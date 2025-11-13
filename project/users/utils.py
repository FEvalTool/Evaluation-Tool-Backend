from .exceptions import TokenNotFoundException
from .models import CustomUser


def generate_username(name):
    """
    Generate username with index

    Parameters
    ----------
    name: str: full name

    Returns
    -------
    str: user name with index

    """
    # Preprocess name have multiple whitespace
    preprocess_name = " ".join(name.split())
    # Getting username prefix (for example Tran Anh Vu => VuTA)
    name_part = preprocess_name.split(" ")
    prefix_username = (
        f"{name_part[-1].capitalize()}{''.join([part[0] for part in name_part[0:-1]])}"
    )
    # Get all user have the same prefix_username
    username_pattern = f"^{prefix_username}(\d+)?$"
    users = CustomUser.objects.filter(username__regex=username_pattern)
    # Return username with index
    return f"{prefix_username}{len(users)+1}"


def get_token_from_cookie(request, cookie_name):
    """
    Extract token from cookie

    Parameters
    ----------
    request: HttpRequest
        The HTTP request object.
    cookie_name: str
        The name of the cookie to extract the token from.

    Returns
    -------
    str or None
        The token if found, otherwise None.
    """
    token = request.COOKIES.get(cookie_name)
    if not token:
        raise TokenNotFoundException(f"Token not found in cookie: {cookie_name}")
    return token
