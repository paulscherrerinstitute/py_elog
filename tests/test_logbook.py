import unittest
# import logging
import elog
from elog.logbook_exceptions import *



class TestClass(unittest.TestCase):

    # TODO add test for delete
    # TODO add description how to run the test docker container for testing

    elog_hostname = 'https://elog.psi.ch/elogs/Linux+Demo/'
    message = 'This message text is new'

    def test_get_message_ids(self):
        logbook = elog.open(self.elog_hostname)
        message_ids = logbook.get_message_ids()
        
    def test_get_last_message_id(self):

        logbook = elog.open(self.elog_hostname)
        msg_id = logbook.post(self.message, attributes={'Author': 'AB', 'Type': 'Routine'})
        message_id = logbook.get_last_message_id()
        self.assertEqual(msg_id, message_id, "Created message does not show up as last edited message")

    def test_get_last_message_id_with_short_timeout(self):

        logbook = elog.open(self.elog_hostname)
        self.assertRaises(LogbookServerTimeout,  logbook.post,
                          self.message, attributes={'Author': 'AB', 'Type': 'Routine'}, timeout=0.01)

    def test_edit(self):
        logbook = elog.open(self.elog_hostname)
        logbook.post('hehehehehe', msg_id=logbook.get_last_message_id(), attributes={"Subject": 'py_elog test [mod]'})

    def test_search(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search("message")
        
    def test_search_empty(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search("")
        
    def test_search_dict(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search({"Category": "Hardware"})
        
    def test_post_special_characters(self):
        logbook = elog.open(self.elog_hostname)
        attributes = { 'Author' : 'Me', 'Type' : 'Other', 'Category' : 'General', 
                      'Subject' : 'This is a test of UTF-8 characters like èéöä'}
        message = 'Just to be clear this is a general test using UTF-8 characters like èéöä.'  
        msg_id = logbook.post(message, reply=False, attributes=attributes, encoding='HTML')
        read_msg, read_attr, read_att = logbook.read(msg_id)
        
        mess_ok = message == read_msg

        attr_ok = True
        for key in attributes:
            if attributes[key] == read_attr[key]:
                attr_ok = attr_ok and True
            else:
                attr_ok = attr_ok and False

        whole_test = attr_ok and mess_ok
        
        self.assertTrue(whole_test)
        
if __name__ == '__main__':
    unittest.main()
    