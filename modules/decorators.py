import logging
import functools

from typing import Callable, Any

logger = logging.getLogger(__name__)

def log_errors(func: Callable) -> Callable:
    """
    A decorator that logs exceptions raised during the execution of the decorated function.

    Parameters
    ----------
    func : Callable
        The function to be decorated.

    Returns
    -------
    Callable
        A wrapped function that logs errors and re-raises them.

    Raises
    ------
    Exception
        Any exception raised by the wrapped function is logged and re-raised.

    Notes
    -----
    This decorator logs the exception and its traceback using the logger before the exception is re-raised.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Błąd w {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

def handle_exceptions(func: Callable) -> Callable:
    """
    A decorator that catches and logs exceptions raised during the execution of the decorated function, 
    returning None instead of propagating the exception.

    Parameters
    ----------
    func : Callable
        The function to be decorated.

    Returns
    -------
    Callable
        A wrapped function that logs errors and returns None.

    Notes
    -----
    If an exception is raised in the wrapped function, it will be logged and `None` will be returned instead 
    of the exception being raised.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return None
    return wrapper

def ensure_connected(func: Callable) -> Callable:
    """
    A decorator that ensures the client is connected before executing the decorated function. 
    If the client is not connected, it attempts to connect to AIMP.

    Parameters
    ----------
    func : Callable
        The function to be decorated.

    Returns
    -------
    Callable
        A wrapped function that ensures the client is connected before execution.

    Notes
    -----
    The decorator checks if `self.client` is `None`. If it is, it calls the `connect_to_aimp` method 
    to establish a connection before executing the wrapped function.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.client:
            self.connect_to_aimp()
        return func(self, *args, **kwargs)
    return wrapper

