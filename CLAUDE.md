# docstrings

If you have to update the docstring of a function, do this according to this template:

    """
    Continue or Exit (CoE)

    This function simplifies error handling for function calls that return a `(success, result)`
    tuple. If the operation fails, it sanitizes and prints the error message and exits with a given
    state. Otherwise, it returns the successful result and allows the script to continue.

    ### Parameters
    - **result** (`tuple`): A two-element tuple returned from a function.
      - `result[0]` (`bool`): Success indicator (`True` if successful, `False` otherwise).
      - `result[1]` (`any`): The actual result or an error message.
    - **state** (`int`, optional): Exit code to use if the function fails.
      Defaults to `STATE_UNKNOWN` (3).

    ### Returns
    - **any type**: The second element of the result tuple (`result[1]`) if successful.

    ### Notes
    - Sensitive information in error messages is automatically redacted before printing.
    - This function is intended to be used **only** inside the `main()` function of a plugin,
      not inside library functions.
    - If the function fails (`result[0]` is `False`), the script immediately exits after printing
      the sanitized message.

    ### Example
    Without `coe`:
    >>> success, html = lib.url.fetch(URL)
    >>> if not success:
    >>>     print(html)
    >>>     sys.exit(STATE_UNKNOWN)

    With `coe`:
    >>> html = lib.base.coe(lib.url.fetch(URL))
    """

Don't exceed 100 characters per line.
