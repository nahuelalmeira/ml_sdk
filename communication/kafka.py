import time
import json
import random
import socket
import msgpack
import logging
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from dataclasses import dataclass
from typing import Dict
from ml_sdk.communication import DispatcherInterface, WorkerInterface
from ml_sdk.model import MLModelInterface

logger = logging.getLogger(__name__)
REPLICATION_FACTOR = 1
PARTITIONS = 20


@dataclass
class KafkaSettings:
    topic: str
    dns: str
    port: int = '9092'

    @property
    def server_uri(self):
        return f'{self.dns}:{self.port}'
    
    @property
    def producer_conf(self):
        conf = {'bootstrap.servers': self.server_uri,
                'client.id': socket.gethostname()}
        return conf
    
    @property
    def consumer_conf(self):
        conf = {'bootstrap.servers': self.server_uri,
                'group.id': "kafka",
                'auto.offset.reset': 'smallest'}
        return conf

    @property
    def manager_conf(self):
        conf = {'bootstrap.servers': self.server_uri}
        return conf

class KafkaNode:
    def __init__(self, settings: KafkaSettings):
        self.manager = AdminClient(settings.manager_conf)
        self.producer = Producer(settings.producer_conf)
        self.consumer = Consumer(settings.consumer_conf)
        self.stop = False

    def init_topics(self, topics):
        new_topics = [
            NewTopic(topic,
                     num_partitions=PARTITIONS,
                     replication_factor=REPLICATION_FACTOR)
            for topic in topics]

        fs = self.manager.create_topics(new_topics)
        
        for topic, f in fs.items():
            try:
                f.result()
                logger.info("Topic {} created".format(topic))
            except Exception as e:
                logger.warning("Topic not created {}: {}".format(topic, e))
    
    @staticmethod
    def _decode(msg):
        return msgpack.unpackb(msg, use_list=False, raw=False)

    @staticmethod
    def _encode(msg):
        return msgpack.packb(msg, use_bin_type=True)

    def stop(self):
        self.stop = True
        self.manager.close()
        self.producer.close()
        self.consumer.close()

    def _produce(self, message, key=None):
        self.producer.produce(self.topic_out, key=key, value=self._encode(message))
    
    def _consume(self, key=None):
        self.consumer.subscribe([self.topic_in])

        while not self.stop:
            msg = self.consumer.poll(timeout=10)
            if msg is None: continue
            if msg.error(): continue
            if key and msg.key().decode() != key: continue
            # self.consumer.commit(async=False)
            return msg.key(), self._decode(msg.value())

class KafkaWorker(KafkaNode, WorkerInterface):
    def __init__(self, settings: KafkaSettings, handler: MLModelInterface):
        super(KafkaWorker, self).__init__(settings)
        self.handler = handler
        self.topic_in = f"{settings.topic}_req"
        self.topic_out = f"{settings.topic}_res"
        self.init_topics([self.topic_in, self.topic_out])

class KafkaDispatcher(KafkaNode, DispatcherInterface):
    def __init__(self, settings: KafkaSettings):
        super(KafkaDispatcher, self).__init__(settings)
        self.stop = False
        self.topic_in = f"{settings.topic}_res"
        self.topic_out = f"{settings.topic}_req"
        self.init_topics([self.topic_in, self.topic_out])