import functools
import traceback

error_trace = []

def log_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            error_trace.append(f'{func.__name__}')
            raise
    return wrapper

@log_error
def func_a():
    return func_b()

@log_error
def func_b():
    return fun_c()

@log_error
def fun_c():
    raise Exception("An error occurred in fun_c")

if __name__ == "__main__":
    try:
        func_a()
    except Exception as e:
        # print error trace from the bottom to the top
        print("Error Trace:", end=' ')
        for trace in reversed(error_trace): print(trace, end=' -> ')
        print(e)
        print()
        print(traceback.format_exc())
