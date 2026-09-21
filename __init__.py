"""Marks this directory as the `lib` package, so a consumer can `import lib.base`.

The modules are independent of each other wherever they can be: a consumer that only
wants `lib.human` pulls in nothing else.
"""
