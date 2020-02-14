import json
import pickle
import uuid

from descriptors import CollectionDescriptor, HashNameDescriptor
from json_util import JSONEncoder, JSONDecoder, MongoJSONEncoder, MongoJSONDecoder


class SerializableObject:

    json_encoder = JSONEncoder
    json_decoder = JSONDecoder

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @property
    def _cls(self):
        return self.__class__

    def to_dict(self):
        return vars(self)

    def to_json(self, **kwargs):
        encoder = kwargs.pop('cls', self.__class__.json_encoder)
        return json.dumps(self.to_dict(), cls=encoder, **kwargs)

    def to_pickle(self):
        return pickle.dumps(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    @classmethod
    def from_json(cls, j, **kwargs):
        decoder = kwargs.pop('cls', cls.json_decoder)
        d = json.loads(j, cls=decoder, **kwargs)
        return cls.from_dict(d)

    @classmethod
    def from_pickle(cls, p):
        instance = pickle.loads(p)
        if type(instance) != cls:
            raise TypeError
        return instance


class Model(SerializableObject):

    def __eq__(self, other):
        if not isinstance(other, Model):
            return NotImplemented

        if type(self) != type(other):
            return False

        if self.pk is None:
            return self is other

        return self.pk == other.pk

    def __hash__(self):
        if self.pk is None:
            raise TypeError("Model instances without a primary key value are unhashable")
        return hash(self.pk)

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, self)

    def __str__(self):
        return "{} object ({})".format(self.__class__.__name__, self.pk)

    @property
    def pk(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    def update(self, data):
        self.__dict__.update(data)

    @classmethod
    def get_by_id(cls, id):
        raise NotImplementedError

    @classmethod
    def get_many(cls, **kwargs):
        raise NotImplementedError


class MongoModel(Model):

    json_encoder = MongoJSONEncoder
    json_decoder = MongoJSONDecoder

    database = None
    collection = CollectionDescriptor()

    @property
    def pk(self):
        try:
            return self._id 
        except AttributeError:
            return None

    def delete(self):
        self._cls.collection.delete_one({'_id': self.pk})

    def save(self):
        if self.pk is None:
            result = self._cls.collection.insert_one(self.to_dict())
            self._id = result.inserted_id
        else:
            self._cls.collection.update_one(
                {'_id': self.pk}, 
                {'$set': self.to_dict()}
            )

    @classmethod
    def get_by_id(cls, id):
        try:
            object_id = ObjectId(id)
        except InvalidId:
            object_id = id

        document = cls.collection.find_one({'_id': object_id})
        if document is not None:
            return cls.from_dict(document)
        return None

    @classmethod
    def get_many(cls, **kwargs):
        cursor = cls.collection.find(kwargs)
        return [cls.from_dict(document) for document in cursor]


class RedisModel(Model):

    connection = None
    hash_name = HashNameDescriptor()

    @property
    def pk(self):
        try:
            return self._key
        except AttributeError:
            return None

    def delete(self):
        return self._RedisModel__delete()

    def save(self):
        return self._RedisModel__save()

    def __delete(self):
        pk = str(self.pk)
        self._cls.connection.hdel(self._cls.hash_name, pk)

    def __save(self):
        if self.pk is None:
            self._key = uuid.uuid4()
        pk = str(self.pk)
        self._cls.connection.hset(self._cls.hash_name, pk, self.to_pickle())

    @classmethod
    def get_by_id(cls, id):
        return cls._RedisModel__get_by_id(id)

    @classmethod
    def __get_by_id(cls, id):
        p = cls.connection.hget(cls.hash_name, id)
        if p is not None:
            return cls.from_pickle(p)
        return None


class HybridModel(MongoModel, RedisModel):
    
    def delete(self):
        super().delete()
        super()._RedisModel__delete(self)

    def save(self):
        super().save()
        super()._RedisModel__save(self)

    @classmethod 
    def get_by_id(cls, id):
        instance = cls._RedisModel__get_by_id(id)
        if instance is None:
            instance = super().get_by_id(id)
        return instance

