import unittest
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

    def test_hierarchy_navigation(self):

        # first generate the hierarchical tree
        logbook = elog.open(self.elog_hostname)
        anchestors = []
        descendants = []
        siblings = []

        attributes = {'Author': 'py_elog',
                      'Type': 'Other',
                      'Category': 'General',
                      'Subject':'Top level'}
        message = 'Hierarchical navigation test performed by the py_elog suite'
        top_level = logbook.post(message, reply=False, attributes=attributes, encoding='HTML')

        attributes['Subject'] ='Sub level 1.1'
        sublevel1_1 = logbook.post(message, reply=True, msg_id=top_level, attributes=attributes, encoding='HTML')
        descendants.append(sublevel1_1)
        siblings.append(sublevel1_1)

        attributes['Subject'] ='Sub level 1.2'
        sublevel1_2 = logbook.post(message, reply=True, msg_id=top_level, attributes=attributes, encoding='HTML')
        descendants.append(sublevel1_2)
        siblings.append(sublevel1_2)

        attributes['Subject'] ='Sub level 1.3'
        sublevel1_3 = logbook.post(message, reply=True, msg_id=top_level, attributes=attributes, encoding='HTML')
        descendants.append(sublevel1_3)
        siblings.append(sublevel1_3)

        attributes['Subject'] ='Sub level 2.1'
        sublevel2_1 = logbook.post(message, reply=True, msg_id=sublevel1_1, attributes=attributes, encoding='HTML')
        descendants.append(sublevel2_1)

        attributes['Subject'] ='Sub level 2.2'
        sublevel2_2 = logbook.post(message, reply=True, msg_id=sublevel1_2, attributes=attributes, encoding='HTML')
        descendants.append(sublevel2_2)

        attributes['Subject'] ='Sub level 2.3'
        sublevel2_3 = logbook.post(message, reply=True, msg_id=sublevel1_3, attributes=attributes, encoding='HTML')
        descendants.append(sublevel2_3)

        attributes['Subject'] = 'Sub level 3.1'
        sublevel3_1 = logbook.post(message, reply=True, msg_id=sublevel2_1, attributes=attributes, encoding='HTML')
        descendants.append(sublevel3_1)

        attributes['Subject'] = 'Sub level 3.2'
        sublevel3_2 = logbook.post(message, reply=True, msg_id=sublevel2_2, attributes=attributes, encoding='HTML')
        descendants.append(sublevel3_2)

        attributes['Subject'] = 'Sub level 3.3'
        sublevel3_3 = logbook.post(message, reply=True, msg_id=sublevel2_3, attributes=attributes, encoding='HTML')
        descendants.append(sublevel3_3)

        anchestors.append(sublevel2_3)
        anchestors.append(sublevel1_3)
        anchestors.append(top_level)


        test_descendants = logbook.get_descendants(top_level)
        test_anchestors = logbook.get_ancestors(sublevel3_3)
        test_siblings = logbook.get_siblings(sublevel1_1)

        self.assertEqual(test_descendants.sort(), descendants.sort())
        self.assertEqual(test_anchestors, anchestors)
        self.assertEqual(test_siblings, siblings)


if __name__ == '__main__':
    unittest.main()
    