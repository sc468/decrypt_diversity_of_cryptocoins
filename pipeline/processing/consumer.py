# -*- coding: utf-8 -*-
#

import os
import sys
import time
import json
import threading
import pyspark_cassandra
from pyspark import SparkContext
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils
from cassandra.cluster import Cluster
import config


CASSANDRA_DNS = config.STORAGE_CONFIG['PUBLIC_DNS']
KEYSPACE = 'cryptcoin'
TABLE_NAME = 'PriceInfo'

ZK_DNS = config.INGESTION_CONFIG['ZK_PUBLIC_DNS']
BATCH_DURATION = 10

GRIUP_ID = 'spark-streaming'
TOPIC = 'CoinsInfo'
NO_PARTITION = 10



def connect_to_cassandra(cassandra_dns=CASSANDRA_DNS, keyspace=KEYSPACE):
    cluster = Cluster([cassandra_dns])
    session = cluster.connect()
    session.set_keyspace(keyspace)
    return session


def create_table(session, table_name=TABLE_NAME):
    query = ("""
        CREATE TABLE IF NOT EXISTS {Table_Name} (
            id text,
            time timestamp,
            price_usd float,
            price_btc float,
            volume_usd_24h float,
            market_cap_usd float,
            available_supply float,
            total_supply float,
            max_supply float,
            percent_change_1h float,
            percent_change_24h float,
            percent_change_7d float,
            PRIMARY KEY ((id), time),
        ) WITH CLUSTERING ORDER BY (time DESC);
    """).format(Table_Name = table_name).translate(None, '\n')
    table_creation_preparation = session.prepare(query)
    session.execute(table_creation_preparation)


def prepare_insertion(session, table_name=TABLE_NAME):
    query = ("""
        INSERT INTO {Table_Name} (
            id,
            time,
            price_usd,
            price_btc,
            volume_usd_24h,
            market_cap_usd,
            available_supply,
            total_supply,
            max_supply,
            percent_change_1h,
            percent_change_24h,
            percent_change_7d
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """).format(Table_Name = table_name).translate(None, '\n')
    return session.prepare(query)


def save_to_cassandra(rdd, session, query_cassandra):
    jsdata = json.loads(rdd)
    session.execute(query_cassandra, (\
            jsdata['id'], \
            jsdata['time'], \
            jsdata['price_usd'], \
            jsdata['price_btc'], \
            jsdata['24h_volume_usd'], \
            jsdata['market_cap_usd'], \
            jsdata['available_supply'], \
            jsdata['total_supply'], \
            jsdata['max_supply'], \
            jsdata['percent_change_1h'], \
            jsdata['percent_change_24h'], \
            jsdata['percent_change_7d'] ))


def main(argv=sys.argv):
    sc = SparkContext(appName='Processing_CoinsInfo')
    sc.setLogLevel("WARN")
    ssc = StreamingContext(sc, BATCH_DURATION)

    session = connect_to_cassandra(CASSANDRA_DNS, KEYSPACE)
    create_table(session, TABLE_NAME)
    # query_cassandra = prepare_insertion(session, TABLE_NAME)


    kafkaStream = KafkaUtils.createStream(ssc, ZK_DNS, GRIUP_ID, {TOPIC : NO_PARTITION})
    kafkaStream.map(lambda (time, records): json.loads(records)) \
                .foreachRDD(lambda rdd: rdd.saveToCassandra(KEYSPACE, TABLE_NAME))


    ssc.start()


if __name__ == "__main__":
    main()
