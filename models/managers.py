from bson.objectid import ObjectId


class Manager:
    def __get__(self, instance, owner):
        if not hasattr(self, 'owner'):
            self.owner = owner
        return self

    def __set__(self, instance, value):
        raise AttributeError


class CollectionManager(Manager):
    def __get__(self, instance, owner):
        return owner.database[owner.__name__.lower()]


class MongoManager(Manager):
    def find(self, *args, **kwargs):
        query = kwargs
        projection = dict.keys(args, True)
        cursor = self.owner.collection.find(query, projection)
        return [self.owner(**document) for document in cursor]

    def find_one(self, *args, **kwargs):
        query = kwargs
        projection = dict.keys(args, True)

        pk = query.pop('pk', None)
        if pk:
            query['_id'] = ObjectId(pk)

        document = self.owner.collection.find_one(query, projection)
        if document is None:
            return None
        return self.owner(**document)


class RedisManager(Manager):
    def get(self, key):
        value = self.owner.connection.get(key)
        if value:
            return self.owner.from_pickle(value)
        return None

    def mget(self, keys):
        values = self.owner.connection.mget(keys)
        return [self.owner.from_pickle(value) for value in values]

