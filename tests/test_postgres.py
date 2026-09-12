import json
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from backend.adapters.postgres_profiles import PostgresProfiles, configuration, connection
from backend.adapters.profile_store import store
from backend.modules.auth import Problem

class PostgresTest(unittest.TestCase):
    def fake(self,row):
        calls=[]
        class DB:
            def execute(self,sql,params):calls.append((sql,params));return self
            def fetchone(self):return row
        @contextmanager
        def factory(**kwargs):
            calls.append(kwargs);yield DB()
        return PostgresProfiles(factory),calls
    def test_read_binds_owner_event_and_preserves_general_without_event(self):
        adapter,calls=self.fake(({'name':'Alex'},None,None))
        self.assertEqual(adapter.get('owner','event'),{'name':'Alex','visible':True,'saved':False})
        self.assertEqual(calls[0],{'read_only':True})
        self.assertEqual(calls[1][1],('event','owner'))
    def test_empty_event_data_still_counts_as_saved(self):
        adapter,_=self.fake(({'name':'Alex'},{},False))
        self.assertEqual(adapter.get('u','e'),{'name':'Alex','visible':False,'saved':True})
    def test_atomic_save_uses_bound_rpc_parameters(self):
        adapter,calls=self.fake(None)
        adapter.save("u'",'e',{'name':'Alex'},{'purpose':'Build'},True)
        sql,params=calls[1]
        self.assertIn('o2c_save_profile',sql);self.assertNotIn("u'",sql)
        self.assertEqual(json.loads(params[2]),{'name':'Alex'})
    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ,{'PROFILE_STORE':'postgres','SUPABASE_DB_URL':''}):
            self.assertIsInstance(store(),PostgresProfiles)
            self.assertFalse(configuration()[2])
            with self.assertRaises(Problem) as raised:
                with connection():pass
            self.assertEqual(raised.exception.status,503)
    def test_failures_redact_driver_credentials(self):
        with patch('backend.adapters.postgres_profiles.configuration',return_value=('private-dsn','ca',True)), patch('psycopg.connect',side_effect=RuntimeError('private-dsn password')):
            with self.assertRaises(Problem) as raised:
                with connection():pass
            self.assertNotIn('private-dsn',raised.exception.message)
