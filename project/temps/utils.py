def get_sort_query(model, request_query_params):
    """
    This function get sort query from query params
    Example:
    model: Student(id, student_name)
    request_query_params: {
        'sort_keys': ['abc', 'student_name']
        'sort_values': [1, -1]
    }
    Return: ['-student_name']

    Parameters
    ----------
        model: Model: model use to get reference fields
        request_query_params: dict: request query params

    Returns
    -------
        bool: True if the user has the required permission, False otherwise.

    """
    model_field_name = [field.name for field in model._meta.get_fields()]
    order_query = []
    for sort_key, sort_order in zip(
        request_query_params["sort_keys"], request_query_params["sort_orders"]
    ):
        if sort_key in model_field_name:
            order_query.append(f"-{sort_key}" if sort_order == -1 else sort_key)
    return order_query
