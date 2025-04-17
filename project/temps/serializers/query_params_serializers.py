from rest_framework import serializers

from ..constants import DEFAULT_PAGE_INDEX, DEFAULT_PAGE_SIZE


class QueryParamsSerializer(serializers.Serializer):
    page_size = serializers.IntegerField(required=False, default=DEFAULT_PAGE_SIZE)
    page_index = serializers.IntegerField(required=False, default=DEFAULT_PAGE_INDEX)
    sort_keys = serializers.ListSerializer(
        child=serializers.CharField(), required=False, default=[]
    )
    sort_orders = serializers.ListSerializer(
        child=serializers.IntegerField(), required=False, default=[]
    )
    all = serializers.BooleanField(required=False, default=False)

    def validate_sort_orders(self, values):
        value_set = set(values)
        if not value_set.issubset({1, -1}):
            raise serializers.ValidationError("Sort orders must be 1 or -1")
        return values

    def validate(self, data):
        if len(data["sort_keys"]) != len(data["sort_orders"]):
            raise serializers.ValidationError(
                "Sort keys and Sort values must have same length"
            )
        return data
