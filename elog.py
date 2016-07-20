class Logbook(object):
    '''
    Logbook: server:port/subdir/logbook

    Logbook object holds a list of existing Message() instances. If post_msg is called and message with msg_id
    already exists it will be updated and returned.
    '''
    def __init__(self, logbook, hostname, port=None, user=None, password=None, subdir='', use_ssl=True):
        '''

        :param logbook: name of the logbook on the elog server
        :param hostname: elog server hostname
        :param port: elog server port (if not specified will default to '80' if use_ssl=False or '443' if use_ssl=True
        :param user: username (if authentication needed)
        :param password: password (if authentication needed)
        :param subdir: subdirectory of logbooks locations
        :param use_ssl: connect using ssl?
        :return:
        '''
        pass

    def post_msg(self, message, msg_id=None, reply=False, attributes=None, attachments=None, encoding='plain', **kwargs):
        '''

        :param message: string with message text or an existing Message()
        :msg_id: Id of message to edit or reply. If not specified new message is created
        :reply: Do reply on existing message (new is created). Else edit existing.
        :param attributes: dictionary of attributes !! Following attributes name are not valid and will be ignored
            because they are used internally by the elog: Text, Date, Encoding, Reply to, In reply to, Locked by,
            Attachment
        :param attachments: list of:
                                  - file like objects which read() will return bytes
                                  - path to the file

                            If there is no attribute flo.name, it will be generated as attributeX.
                            All objects will be appended as attachment to the elog entry.
        :param encoding: can be: 'plain' -> plain text, 'html'->html-text, 'ELCode' --> elog formatting syntax
        :param kwargs: Since there are basically no mandatory fields for logbook(totally depends on the
                       specific logbook configurations) anything in the kwargs will be interpreted as attributes.
                       e.g.: Elog.post_msg('Test text', Author='Rok Vintar), "Author" will be sent as an attribute
                       If named same as one of the attributes defined in "attributes", kwargs will have priority.

        Error handling with exceptions

        :return: Message()
        '''

        pass


    def read_msg(self, msg_id):
        '''
        Reads message from the logbook
        :param msg_id: id of message to read from the logbook
        :return: Message()
        '''



class Message(object):
    '''
    Has following standard attributes:

    logbook: instance of the "parent" Logbook
    msg_id: (uint) unique message id on the logbook (if None, new entry will be created with first post()
    message: string with message text
    attributes: dictionary of attributes. Key: attribute name, value: (string) value of the attribute
    attachments: list of all message attributes. Can be:
                   - file like object returning bytes on read()
                   - path to the file
                   - url to existing attachments (all types of attachments will be "changed" to this type
                                                  once message is posted)
    encoding: can be: 'plain' -> plain text, 'html'->html-text, 'ELCode' --> elog formatting syntax


    '''
    def __init__(self, logbook, msg_id=None, message='', attributes=None, attachments=None, encoding='plain', **kwargs):
        '''
        logbook
        If msg_id is specified

        Same param description as for Logbook.post_msg(), except:
           - logbook is logbook instance
           - message can be only a string

        All parameters results in equally named object attributes
        '''
        self.msg_id = msg_id
        self.logbook = logbook
        self.message = message
        self.attributes = attributes  # After first get or post
        self.attachments = attachments

        self.__dict__.update(kwargs)


    def post(self):
        '''
        Calls logbook.post_msg(). All none standard (msg_id, logbook, message, attributes, attachments)
        object attributes (except those with a leading underscore) are sent as kwargs and added to attributes.
        In case of attribute (e.g. atr1) being defined in message.attributes list and as message.atr1 the message.atr1
        will be used.
        :return:
        '''
        ## logbook.post_msg()
        pass

    def read(self):
        '''
        This method updates all arguments with values from the logbook. Any object attribute (e.g. Message.Author)
        that corresponds to message attribute, is also updated.
        :return:
        '''

    def post_reply(self,  message='', attributes=None, attachments=None, encoding='plain', quote=False **kwargs):
        '''
        New message object will be created and posted as reply to current message.
        :param message:
        :param attributes:
        :param attachments:
        :param encoding:
        :param quote: quote current
        :param kwargs:
        :return: reply Message() instance
        '''




