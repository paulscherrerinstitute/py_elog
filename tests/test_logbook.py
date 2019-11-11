import unittest
# import logging
import elog

# logging.basicConfig(level=logging.DEBUG)


class TestClass(unittest.TestCase):

    # TODO add test for delete
    # TODO add description how to run the test docker container for testing

    def test_read(self):

        logbook = elog.open('https://elog-gfa.psi.ch/SwissFEL+test/')
        message, attributes, attachments = logbook.read(23)
        print(message)
        self.assertEqual(message, 'Test from shell', "Unable to retrieve message")

    def test_get_message_ids(self):
        logbook = elog.open('https://elog-gfa.psi.ch/SwissFEL+test/')
        message_ids = logbook.get_message_ids()
        print(len(message_ids))
        print(message_ids)

    def test_get_last_message_id(self):

        logbook = elog.open('https://elog-gfa.psi.ch/SwissFEL+test/')
        msg_id = logbook.post('This is message text is new')
        message_id = logbook.get_last_message_id()

        print(msg_id)
        print(message_id)
        self.assertEqual(msg_id, message_id, "Created message does not show up as last edited message")

    def test_edit(self):
        logbook = elog.open('https://elog-gfa.psi.ch/SwissFEL+test/')
        logbook.post('hehehehehe', msg_id=55, attributes={"Title": 'A new one BLABLA', "When": 1510657172})


if __name__ == '__main__':
    unittest.main()
