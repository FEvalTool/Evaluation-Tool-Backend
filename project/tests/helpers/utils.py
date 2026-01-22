# This function is retrieving error key list
# from validation error response
def get_error_key_response(response):
    error_item_keys = []
    if "error" in response.json():
        for error in response.json()["error"]:
            error_item_keys.extend(list(error.keys()))
    return error_item_keys
