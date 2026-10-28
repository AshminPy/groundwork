class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def put(self, key, value):
        if key in self._data:
            del self._data[key]
        self._data[key] = value
        if len(self._data) > self.capacity:
            oldest = next(iter(self._data))
            del self._data[oldest]
