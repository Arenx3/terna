"""A résumé against a job's requirements: a verdict for each one, with its evidence.

Three kinds of signal, each shown to the recruiter with what it found:

- Keywords: the requirement's skills, with their aliases from the dictionary
  ("k8s" is Kubernetes), and its other content words, looked up in the résumé.
- Meaning: how close each passage is to the requirement according to a local
  multilingual model, so "Opero los clústeres de Kubernetes" answers
  "Kubernetes in production".
- Rules: years of experience counted from the dates of the roles that match,
  and a language level compared with the one asked for.

Pure functions over redacted passages (`screening.analysis`): the task loads the
inputs and stores what comes out. Every position points into the passage's
original text, so the screen can highlight the evidence where it is.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from functools import cache

from screening import dictionary, gazetteer
from screening.analysis import MASK, AnalysisPassage
from screening.models import Section, Verdict
from screening.redaction import fold

# Bump when the rules or thresholds change: every screening is done again.
VERSION = 1

# Cosine similarity between a requirement and a passage (multilingual MiniLM), measured
# on the demo résumés: unrelated lines about work reach 0.45, so meaning alone needs 0.5
# to count as partial evidence and 0.7 to meet a requirement. Below that, 0.35 still
# backs up a skill the keywords already found ("Kubernetes" in a line about clusters).
SEMANTIC_HIGH = 0.70
SEMANTIC_LOW = 0.50
SEMANTIC_SUPPORT = 0.35
MAX_EVIDENCE = 4

# The summary is a weighted count, shown with its formula: a must-have weighs twice a
# nice-to-have, and partly meeting one earns half of it.
WEIGHTS = {"must": 2, "nice": 1}
PARTIAL_CREDIT = 0.5

STRONG, MEDIUM, SOME, NONE = "strong", "medium", "some", "none"

TOKEN = re.compile(r"[a-z0-9](?:[a-z0-9+#.]*[a-z0-9+#])?")
# Words that say nothing about the skill itself.
STOPWORDS = gazetteer.words(
    """
    a al an and as at by con de del desde e el en for from in into is la las lo los o of on
    or para por que the to u un una unos unas with y su sus our your their its experiencia
    experience experiencias anos ano years year yrs minimo minimum least menos mas more than
    over plus deseable preferred preferible ideal ideally requerido required manejo uso use
    using conocimiento conocimientos knowledge nivel level niveles solido solida solid
    strong buen buena good excelente excellent habilidad habilidades skill skills capacidad
    ability trabajo work working herramienta herramientas tool tools demostrable proven
    comprobable hands on similar equivalente equivalent alguno alguna some any ser estar
    have has having tener contar etc other others otro otra otros otras demas new nuevo
    nueva nuevos nuevas across within entre sobre about
    """
)

LEVELS = {
    "a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6,
    "basico": 2, "basica": 2, "basic": 2, "elemental": 2, "beginner": 1,
    "intermedio": 3, "intermedia": 3, "intermediate": 3,
    "avanzado": 5, "avanzada": 5, "advanced": 5,
    "fluido": 5, "fluida": 5, "fluent": 5, "fluency": 5, "fluidez": 5,
    "bilingue": 5, "bilingual": 5, "profesional": 5, "professional": 5,
    "nativo": 6, "nativa": 6, "native": 6, "materna": 6,
}  # fmt: skip
LEVEL_NAMES = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1", 6: "C2"}
NUMBERS = {
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
YEARS = re.compile(
    r"(?<![\w.])\+?\s*(?P<n>\d{1,2}|" + "|".join(NUMBERS) + r")\s*\+?\s*"
    r"(?:anos?|years?|yrs?)\b"
)
ALTERNATIVE = re.compile(r"^\s*(?:/|,?\s*(?:o|u|or|y/o|and/or)\s*)$")
# A level stated this far from the language's name belongs to it.
LEVEL_REACH = 30


@dataclass(frozen=True)
class Need:
    """A requirement as matching reads it."""

    id: int
    text: str
    kind: str


@dataclass(frozen=True)
class Tokens:
    """A text as stems, each with where it sits in the text."""

    stems: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]

    def find(self, phrase: tuple[str, ...]) -> list[tuple[int, int]]:
        """Character spans of every place the stemmed phrase appears."""
        size, found = len(phrase), []
        if not size:
            return found
        for index in range(len(self.stems) - size + 1):
            if self.stems[index : index + size] == phrase:
                found.append((self.spans[index][0], self.spans[index + size - 1][1]))
        return found


@cache
def _stemmer(language: str):
    import snowballstemmer

    return snowballstemmer.stemmer("spanish" if language == "es" else "english")


@cache
def stem(word: str, language: str) -> str:
    if not word.isalpha():  # "c++", "4.0", "node.js", "b2b": taken as written
        return word
    return _stemmer(language).stemWord(word)


def tokenize(text: str, language: str) -> Tokens:
    matches = list(TOKEN.finditer(fold(text)))
    return Tokens(
        stems=tuple(stem(match.group(0), language) for match in matches),
        spans=tuple(match.span() for match in matches),
    )


def phrase(text: str, language: str) -> tuple[str, ...]:
    return tokenize(text, language).stems


# The requirement


@dataclass(frozen=True)
class Concept:
    """A dictionary entry, ready to look up in one language."""

    term: str
    key: str
    phrases: tuple[tuple[str, ...], ...]  # the term's first

    @property
    def is_language(self) -> bool:
        return self.key in dictionary.LANGUAGES


def concepts(entries: Iterable[dictionary.Entry], language: str) -> list[Concept]:
    out = []
    for entry in entries:
        phrases = tuple(p for p in (phrase(word, language) for word in entry.words) if p)
        if phrases:
            out.append(Concept(entry.term, entry.key, phrases))
    return out


@dataclass(frozen=True)
class Mention:
    concept: Concept
    label: str  # as the requirement writes it
    start: int
    end: int


@dataclass(frozen=True)
class Term:
    label: str
    word: str  # folded, stemmed again in the résumé's language


@dataclass(frozen=True)
class Parsed:
    # Each group is met by any of its concepts: "Kafka or RabbitMQ" is one group.
    groups: tuple[tuple[Mention, ...], ...]
    terms: tuple[Term, ...]
    years: int | None = None
    level: int | None = None

    @property
    def language(self) -> Mention | None:
        """The language whose level the requirement asks for, if that's what it asks."""
        if self.level is None:
            return None
        for group in self.groups:
            for mention in group:
                if mention.concept.is_language:
                    return mention
        return None


def parse(text: str, language: str, known: list[Concept]) -> Parsed:
    folded = fold(text)
    tokens = tokenize(text, language)
    found: list[tuple[int, int, int, Mention]] = []
    for concept in known:
        for rank, words in enumerate(concept.phrases):
            for start, end in tokens.find(words):
                mention = Mention(concept, text[start:end], start, end)
                # Longest first; for the same words, the entry they name ("PostgreSQL" is
                # PostgreSQL before it's an alias of SQL).
                found.append((-(end - start), min(rank, 1), start, mention))
    mentions: list[Mention] = []
    for *_, mention in sorted(found, key=lambda item: item[:3]):
        if not any(mention.start < m.end and m.start < mention.end for m in mentions):
            mentions.append(mention)
    mentions.sort(key=lambda m: m.start)

    groups: list[list[Mention]] = []
    for mention in mentions:
        previous = groups[-1][-1] if groups else None
        if previous and ALTERNATIVE.match(folded[previous.end : mention.start]):
            groups[-1].append(mention)
        else:
            groups.append([mention])

    years_match = YEARS.search(folded)
    years = None
    taken = [(m.start, m.end) for m in mentions]
    if years_match:
        value = years_match.group("n")
        years = int(value) if value.isdigit() else NUMBERS[value]
        taken.append(years_match.span())

    level = None
    terms: list[Term] = []
    for match in TOKEN.finditer(folded):
        word, (start, end) = match.group(0), match.span()
        if any(start < b and a < end for a, b in taken):
            continue
        if word in LEVELS:
            level = max(level or 0, LEVELS[word])
            continue
        if word in STOPWORDS or word.isdigit() or len(word) < 3:
            continue
        if word not in {t.word for t in terms}:
            terms.append(Term(text[start:end], word))
    return Parsed(tuple(tuple(g) for g in groups), tuple(terms), years, level)


# The résumé


@dataclass
class Page:
    """A passage with its tokens, ready to search."""

    passage: AnalysisPassage
    tokens: Tokens


@dataclass
class Role:
    """A job in the experience section: its dated line and the lines under it."""

    pages: list[Page]

    @property
    def periods(self) -> list[tuple[Page, dict]]:
        return [(page, period) for page in self.pages for period in page.passage.periods]


def _date_only(passage: AnalysisPassage) -> bool:
    rest = passage.masked
    for period in passage.periods:
        rest = rest.replace(period["text"], "")
    return len(re.sub(r"[\W_]+", "", rest)) < 6


WORK_SECTIONS = (Section.EXPERIENCE,)
NOT_WORK = (
    Section.HEADER,
    Section.EDUCATION,
    Section.CERTIFICATIONS,
    Section.LANGUAGES,
    Section.SKILLS,
)


def roles(pages: list[Page]) -> list[Role]:
    work = [p for p in pages if p.passage.section in WORK_SECTIONS]
    if not any(p.passage.periods for p in work):
        # No experience heading with dates: any dated entry outside education will do.
        work = [p for p in pages if p.passage.section not in NOT_WORK]
    out: list[Role] = []
    loose: list[Page] = []
    for page in work:
        if page.passage.periods:
            role = Role([page])
            if _date_only(page.passage):
                # "Engineer, Acme" on one line and its dates on the next.
                source = out[-1].pages if out else loose
                if len(source) > (1 if out else 0):
                    role.pages.insert(0, source.pop())
            out.append(role)
        elif out:
            out[-1].pages.append(page)
        else:
            loose.append(page)
    return out


def _month(label: str, end: bool) -> int:
    year, _, month = label.partition("-")
    if month:
        return int(year) * 12 + int(month) - 1 + (1 if end else 0)
    return int(year) * 12


def covered_months(periods: Iterable[dict], today: date) -> int:
    """Months covered by the periods, counting overlaps once."""
    now = today.year * 12 + today.month
    spans = sorted(
        (
            _month(period["start"], end=False),
            now if period["ongoing"] or not period["end"] else _month(period["end"], end=True),
        )
        for period in periods
    )
    total, current_start, current_end = 0, None, None
    for start, end in spans:
        end = max(end, start + 1)  # "2019 – 2019" still counts a month
        if current_end is None or start > current_end:
            if current_end is not None:
                total += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total += current_end - current_start
    return total


# Judging


@dataclass
class Hit:
    page: Page
    spans: list[tuple[int, int]] = field(default_factory=list)
    signals: set[str] = field(default_factory=set)


@dataclass
class Result:
    need: Need
    verdict: str
    signals: dict
    evidence: list[dict]


@dataclass
class Resume:
    pages: list[Page]
    language: str
    concepts: dict[str, Concept]  # by key, in the résumé's language
    roles: list[Role]

    @classmethod
    def of(cls, passages: list[AnalysisPassage], language: str, known: list[Concept]):
        pages = [Page(p, tokenize(p.masked, language)) for p in passages]
        return cls(pages, language, {c.key: c for c in known}, roles(pages))


def _concept_spans(resume: Resume, mention: Mention, pages: list[Page]) -> dict[int, list]:
    concept = resume.concepts.get(mention.concept.key)
    out: dict[int, list] = {}
    if concept is None:
        return out
    for page in pages:
        for words in concept.phrases:
            spans = page.tokens.find(words)
            if spans:
                out.setdefault(page.passage.id, []).extend(spans)
    return out


def _term_spans(resume: Resume, term: Term, pages: list[Page]) -> dict[int, list]:
    words = (stem(term.word, resume.language),)
    out: dict[int, list] = {}
    for page in pages:
        spans = page.tokens.find(words)
        if spans:
            out[page.passage.id] = spans
    return out


@dataclass
class Keywords:
    level: str
    found: list[dict]
    missing: list[str]
    hits: dict[int, list[tuple[int, int]]]
    groups_met: int


def keywords(parsed: Parsed, resume: Resume, pages: list[Page] | None = None) -> Keywords:
    pages = resume.pages if pages is None else pages
    by_id = {page.passage.id: page for page in pages}
    found, missing, hits = [], [], {}
    groups_met = 0
    for group in parsed.groups:
        met = False
        for mention in group:
            spans = _concept_spans(resume, mention, pages)
            if spans:
                met = True
                first_id = min(spans, key=lambda pid: by_id[pid].passage.position)
                start, end = spans[first_id][0]
                found.append(
                    {"term": mention.label, "matched": by_id[first_id].passage.masked[start:end]}
                )
                for pid, items in spans.items():
                    hits.setdefault(pid, []).extend(items)
        if met:
            groups_met += 1
        else:
            missing.append(" / ".join(m.label for m in group))
    terms_met = 0
    for term in parsed.terms:
        spans = _term_spans(resume, term, pages)
        if spans:
            terms_met += 1
            first_id = min(spans, key=lambda pid: by_id[pid].passage.position)
            start, end = spans[first_id][0]
            found.append({"term": term.label, "matched": by_id[first_id].passage.masked[start:end]})
            for pid, items in spans.items():
                hits.setdefault(pid, []).extend(items)
        else:
            missing.append(term.label)

    groups, terms = len(parsed.groups), len(parsed.terms)
    term_share = terms_met / terms if terms else 1.0
    if groups:
        if groups_met == groups:
            level = STRONG if term_share >= 0.5 else MEDIUM
        else:
            # Without the skill itself, its other words ("engineers") prove nothing.
            level = SOME if groups_met else NONE
    elif terms:
        level = STRONG if term_share >= 0.75 else SOME if term_share >= 0.4 else NONE
    else:
        level = NONE
    return Keywords(level, found, missing, hits, groups_met)


def _level_near(page: Page, start: int, end: int) -> tuple[int, tuple[int, int]] | None:
    """The level stated right after a language's name ("English (C1)"), or right before."""
    folded = fold(page.passage.masked)
    after = [
        m for m in TOKEN.finditer(folded, end, min(len(folded), end + LEVEL_REACH))
        if m.group(0) in LEVELS
    ]  # fmt: skip
    if after:
        return LEVELS[after[0].group(0)], after[0].span()
    before = [
        m for m in TOKEN.finditer(folded, max(0, start - LEVEL_REACH), start)
        if m.group(0) in LEVELS
    ]  # fmt: skip
    if before:
        return LEVELS[before[-1].group(0)], before[-1].span()
    return None


def judge(
    need: Need,
    parsed: Parsed,
    resume: Resume,
    similarity: dict[int, float],
    today: date | None = None,
) -> Result:
    """One requirement's verdict, the signals behind it and the evidence they found."""
    today = today or date.today()
    kw = keywords(parsed, resume)
    by_id = {page.passage.id: page for page in resume.pages}
    # The header is who the person is and where to reach them, not evidence of a skill.
    similarity = {
        pid: score
        for pid, score in similarity.items()
        if pid in by_id and by_id[pid].passage.section != Section.HEADER
    }
    best_id = max(similarity, key=similarity.get) if similarity else None
    best = similarity.get(best_id, 0.0) if best_id is not None else 0.0
    # Meaning that counts on its own, not only as support for the keywords.
    meaningful = best >= SEMANTIC_LOW
    # Support comes from a line that has the words *and* reads like the requirement.
    support_id = max(kw.hits, key=lambda pid: similarity.get(pid, 0.0)) if kw.hits else None
    support = similarity.get(support_id, 0.0) if support_id is not None else 0.0
    if meaningful:
        semantic_level = STRONG if best >= SEMANTIC_HIGH else MEDIUM
        semantic_id, score = best_id, best
    elif support >= SEMANTIC_SUPPORT:
        semantic_level, semantic_id, score = SOME, support_id, support
    else:
        semantic_level, semantic_id, score = NONE, None, best

    hits: dict[int, Hit] = {}

    def add(page_id: int, spans: Iterable[tuple[int, int]], signal: str) -> None:
        hit = hits.setdefault(page_id, Hit(by_id[page_id]))
        hit.spans.extend(spans)
        hit.signals.add(signal)

    signals: dict = {
        "keyword": {"level": kw.level, "found": kw.found, "missing": kw.missing},
        "semantic": {
            "level": semantic_level,
            "score": round(score, 3),
            "passage": None,  # set below, if it's part of the evidence
        },
    }
    language = parsed.language
    if language is not None:
        # Any two lines about languages read alike; only the stated level counts.
        del signals["semantic"]
        verdict = _judge_level(parsed, language, resume, signals, add)
    elif parsed.years is not None:
        verdict = _judge_years(parsed, resume, similarity, kw, meaningful, signals, add, today)
    elif (
        kw.level == STRONG
        or semantic_level == STRONG
        or (kw.level == MEDIUM and semantic_level != NONE)
    ):
        verdict = Verdict.MEETS
    elif kw.level != NONE or meaningful:
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.NO_EVIDENCE

    if verdict != Verdict.NO_EVIDENCE and language is None:
        # Where the words were found, best first, then the closest passage in meaning.
        ranked = sorted(
            kw.hits.items(),
            key=lambda item: (-len(item[1]), -similarity.get(item[0], 0.0)),
        )
        for page_id, spans in ranked:
            add(page_id, spans, "keyword")
        if meaningful:
            # The whole line, but never the personal data hidden in it.
            add(best_id, visible_spans(by_id[best_id].passage.masked), "semantic")
            signals["semantic"]["passage"] = best_id
        elif semantic_level == SOME and kw.level == MEDIUM:
            add(semantic_id, [], "semantic")  # already highlighted by its words
            signals["semantic"]["passage"] = semantic_id
    evidence = [
        {
            "passage": page_id,
            "spans": _merge(hit.spans),
            "signals": sorted(hit.signals),
        }
        for page_id, hit in list(hits.items())[:MAX_EVIDENCE]
    ]
    # No verdict without something to show for it.
    if verdict == Verdict.NO_EVIDENCE or not evidence:
        verdict, evidence = Verdict.NO_EVIDENCE, []
    return Result(need, verdict, signals, evidence)


def _judge_level(parsed: Parsed, language: Mention, resume: Resume, signals: dict, add) -> str:
    required = parsed.level or 0
    stated = None
    spans = _concept_spans(resume, language, resume.pages)
    for page_id, items in sorted(spans.items()):
        page = next(p for p in resume.pages if p.passage.id == page_id)
        for start, end in items:
            near = _level_near(page, start, end)
            if near and (stated is None or near[0] > stated[0]):
                stated = (near[0], page_id, (start, end), near[1])
    if stated is not None:
        level, page_id, name, level_span = stated
        add(page_id, [name, level_span], "level")
        verdict = Verdict.MEETS if level >= required else Verdict.PARTIAL
        found = LEVEL_NAMES[level]
    elif spans:
        page_id = min(spans)
        add(page_id, spans[page_id], "level")
        verdict, found = Verdict.PARTIAL, None
    else:
        verdict, found = Verdict.NO_EVIDENCE, None
    signals["level"] = {
        "language": language.label,
        "required": LEVEL_NAMES[required],
        "found": found,
    }
    return verdict


def _judge_years(
    parsed: Parsed,
    resume: Resume,
    similarity: dict[int, float],
    kw: Keywords,
    meaningful: bool,
    signals: dict,
    add,
    today: date,
) -> str:
    needed = parsed.years * 12
    has_topic = bool(parsed.groups or parsed.terms)
    relevant: list[Role] = []
    for role in resume.roles:
        if not has_topic:
            relevant.append(role)
            continue
        # A role counts if it names at least half of the skills ("APIs in Python": a role
        # in Python counts), or reads like the requirement.
        in_role = keywords(parsed, resume, role.pages)
        close = max((similarity.get(p.passage.id, 0.0) for p in role.pages), default=0.0)
        named = (
            in_role.groups_met * 2 >= len(parsed.groups) if parsed.groups else in_role.level != NONE
        )
        if (named and in_role.found) or close >= SEMANTIC_LOW:
            relevant.append(role)
    months = covered_months((period for role in relevant for _, period in role.periods), today)
    for role in relevant:
        for page, period in role.periods:
            add(page.passage.id, [tuple(period["at"])], "years")
    signals["years"] = {
        "required": parsed.years,
        "months": months,
        "roles": [role.pages[0].passage.id for role in relevant],
    }
    # The years, and the skill itself somewhere in the résumé, in words or in meaning.
    if relevant and months >= needed and (kw.level in (STRONG, MEDIUM) or meaningful):
        return Verdict.MEETS
    # Some of the years, or the skill without dates to count.
    if relevant or (has_topic and (kw.level != NONE or meaningful)):
        return Verdict.PARTIAL
    return Verdict.NO_EVIDENCE


def visible_spans(masked: str) -> list[tuple[int, int]]:
    """The stretches of a passage outside its hidden data, without surrounding spaces."""
    spans = []
    for match in re.finditer(rf"[^{MASK}]+", masked):
        text = match.group(0)
        start = match.start() + len(text) - len(text.lstrip())
        end = match.end() - (len(text) - len(text.rstrip()))
        if any(ch.isalnum() for ch in masked[start:end]):
            spans.append((start, end))
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def screen(
    needs: list[Need],
    passages: list[AnalysisPassage],
    *,
    job_language: str,
    resume_language: str,
    entries: list[dictionary.Entry],
    similarity: dict[int, dict[int, float]],
    today: date | None = None,
) -> list[Result]:
    """Every requirement's verdict. `similarity[need id][passage id]` comes from the model."""
    resume = Resume.of(passages, resume_language, concepts(entries, resume_language))
    known = concepts(entries, job_language)
    return [
        judge(
            need,
            parse(need.text, job_language, known),
            resume,
            similarity.get(need.id, {}),
            today,
        )
        for need in needs
    ]
