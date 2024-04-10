import os

RELATIVE_PATH = "../"

try:
    from dotenv import load_dotenv
    env = os.path.join(os.getcwd(), f"{RELATIVE_PATH}.env")
    # print('Loading environment variables from: ' + env)
    load_dotenv(
        dotenv_path=env,
    )
except ImportError as e:
    print("Running in production (dotenv unused)")


def enforce_env_var(name: str) -> str:
    """
    Enforce that an environment variable is set and return its value.
    """
    value = os.environ.get(name)
    if value is None or len(value) == 0:
        print(f"Required environment variable not set: {name}")
        exit(1)

    return value
