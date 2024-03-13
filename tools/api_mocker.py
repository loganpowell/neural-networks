import json

def api_mocker(endpoint: str, method, payload):
    """
    Mocks the Vertex API
    """
    # if any of the parameters are missing, return an error
    message = json.dumps(
        {'endpoint': endpoint, 'method': method, 'payload': payload})
    if not endpoint or not method or not payload:
        return {
            "status": "error",
            "message": f"Missing parameter(s): { message }"
        }
    if method == "POST":
        return {
            "status": "successful POST request",
            "message": message
        }
    elif method == "GET":
        return {
            "status": "successful GET request",
            "message": message
        }
    elif method == "PUT":
        return {
            "status": "successsful PUT request",
            "message": message
        }
    elif method == "DELETE":
        return {
            "status": "successful DELETE request",
            "message": message
        }
