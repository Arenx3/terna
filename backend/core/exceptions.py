from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """DRF's handler, plus a stable `code` next to `detail`.

    `detail` is localized for people; `code` is what clients branch on and
    translate, so its values never change.
    """
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        if isinstance(codes, str):
            response.data["code"] = codes
    return response
