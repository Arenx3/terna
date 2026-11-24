"""PostgreSQL pieces of tenant isolation: the company setting, policies and roles.

Policies compare a row's company to `app_current_company()`, which reads the
`app.company_id` setting of the current transaction. Nothing set means NULL,
and NULL matches no row: forgetting to choose a company shows nothing.
"""

from django.db.backends.base.base import BaseDatabaseWrapper
from psycopg import sql

COMPANY_SETTING = "app.company_id"
POLICY_NAME = "tenant_isolation"
CURRENT_COMPANY_FUNCTION = "app_current_company"
ALL_COMPANIES_FUNCTION = "app_all_company_ids"


def set_company(connection: BaseDatabaseWrapper, company_id: str) -> None:
    """Set the company for the rest of the current transaction ('' clears it)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [COMPANY_SETTING, company_id])


def get_company(connection: BaseDatabaseWrapper) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT coalesce(current_setting(%s, true), '')", [COMPANY_SETTING])
        return cursor.fetchone()[0]


def _run(connection: BaseDatabaseWrapper, statements: list[sql.Composable]) -> None:
    with connection.cursor() as cursor:
        raw = cursor.connection  # psycopg connection, to render identifiers safely
        for statement in statements:
            cursor.execute(statement.as_string(raw))


def enable_row_level_security(connection: BaseDatabaseWrapper, table: str, column: str) -> None:
    """Idempotent: (re)creates the isolation policy on `table`, keyed by `column`.

    FORCE makes the policy apply to the table owner too, so only superusers and
    roles with BYPASSRLS (the migration role, never the app) can skip it.
    """
    table_id = sql.Identifier(table)
    predicate = sql.SQL("{column} = {function}()").format(
        column=sql.Identifier(column), function=sql.Identifier(CURRENT_COMPANY_FUNCTION)
    )
    _run(
        connection,
        [
            sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(table_id),
            sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(table_id),
            sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(sql.Identifier(POLICY_NAME), table_id),
            sql.SQL("CREATE POLICY {} ON {} USING ({}) WITH CHECK ({})").format(
                sql.Identifier(POLICY_NAME), table_id, predicate, predicate
            ),
        ],
    )


def ensure_app_role(
    connection: BaseDatabaseWrapper, role: str, password: str, database: str
) -> None:
    """Create or update the unprivileged login role the app connects with.

    Runs as the migration role. Utility statements cannot take bind parameters,
    so the password is rendered as a quoted literal.
    """
    role_id = sql.Identifier(role)
    attributes = sql.SQL(
        "LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
    ).format(sql.Literal(password))
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        exists = cursor.fetchone() is not None
    verb = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
    _run(
        connection,
        [
            sql.SQL("{} {} WITH {}").format(verb, role_id, attributes),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), role_id),
        ],
    )


def grant_app_role(connection: BaseDatabaseWrapper, role: str) -> None:
    """Data access for the app role on every table, now and in future migrations.

    Creates the role without login if it does not exist yet (a fresh test
    database), so migrations never depend on the bootstrap having run first.
    """
    role_id = sql.Identifier(role)
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        exists = cursor.fetchone() is not None
    statements = [] if exists else [sql.SQL("CREATE ROLE {} NOLOGIN").format(role_id)]
    statements += [
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_id),
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            role_id
        ),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role_id),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(role_id),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(role_id),
        sql.SQL("GRANT EXECUTE ON FUNCTION {}() TO {}").format(
            sql.Identifier(ALL_COMPANIES_FUNCTION), role_id
        ),
    ]
    _run(connection, statements)
