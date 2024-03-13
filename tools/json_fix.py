import json
import re

def fix_json(json_str: str):
    """
    Try to parse the JSON string, and if it fails, look for the character where
    it failed in the exception string and replace that character.

    You may want to add some additional checks to prevent this from ending in an
    infinite loop (e.g., at max as many repetitions as there are characters in
    the string).

    """
    # source: https://stackoverflow.com/a/18515887
    while True:
        try:
            result = json.loads(json_str)   # try to parse...
            break                    # parsing worked -> exit loop
        except Exception as e:
            # "Expecting , delimiter: line 34 column 54 (char 1158)"
            # position of unexpected character after '"'
            unexp = int(re.findall(r'\(char (\d+)\)', str(e))[0])
            # position of unescaped '"' before that
            unesc = json_str.rfind(r'"', 0, unexp)
            s = json_str[:unesc] + r'\"' + json_str[unesc+1:]
            # position of correspondig closing '"' (+2 for inserted '\')
            closg = s.find(r'"', unesc + 2)
            s = s[:closg] + r'\"' + s[closg+1:]

    print(result)
    return result