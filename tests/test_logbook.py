import unittest
# import logging
import elog




class TestClass(unittest.TestCase):

    # TODO add test for delete
    # TODO add description how to run the test docker container for testing

    elog_hostname = 'https://elog.psi.ch/elogs/Linux+Demo/'


    def test_get_message_ids(self):
        logbook = elog.open(self.elog_hostname)
        message_ids = logbook.get_message_ids()
        print(len(message_ids))
        print(message_ids)

    def test_get_last_message_id(self):

        logbook = elog.open(self.elog_hostname)
        msg_id = logbook.post('This is message text is new', attributes={'Author':'AB', 'Type':'Routine'})
        message_id = logbook.get_last_message_id()

        print(msg_id)
        print(message_id)
        self.assertEqual(msg_id, message_id, "Created message does not show up as last edited message")
        

    def test_read(self):

        logbook = elog.open(self.elog_hostname)
        message, attributes, attachments = logbook.read(logbook.get_last_message_id())
        print(message)
        self.assertEqual(message, 'This is message text is new', "Unable to retrieve message")


    def test_edit(self):
        logbook = elog.open(self.elog_hostname)
        logbook.post('hehehehehe', msg_id=logbook.get_last_message_id(), attributes={"Subject": 'py_elog test [mod]'})

    def test_search(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search("message")
        print(ids)
        
    def test_search_empty(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search("")
        print(ids)
        
    def test_search_dict(self):
        logbook = elog.open(self.elog_hostname)
        ids = logbook.search({"Category": "Hardware"})
        print(ids)

if __name__ == '__main__':
    unittest.main()
