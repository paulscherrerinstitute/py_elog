
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
        pass

    def read(self):
        '''
        This method updates all arguments with values from the logbook. Any object attribute (e.g. Message.Author)
        that corresponds to message attribute, is also updated.
        :return:
        '''
        pass

    def post_reply(self,  message='', attributes=None, attachments=None, encoding='plain', quote=False, **kwargs):
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
        pass



