# Overview
This python module provides a interface to [electronic logbooks](https://midas.psi.ch/elog/). It is compatible with python versions 3.5 and higher.

# Quick start
> This is a quick intro into using an elog module, for detailed information about specific methods, please consult section [Methods](#Methods).

For each logbook (http[s]://<hostename>:<port>/[<subdir>/]<logbook>/[<msg_id>]) that needs to be accessed, either for reading or posting messages, a new logbook object must be created ()
```python
import elog 

# demo logbook on local host: http://localhost:8080/demo/
demo_logbook = elog.open('localhost', 'demo', port=8080, use_ssl=False)

# shorter version
# psi-gfa logbook:
gfa_logbook = elog.open('https://elog-gfa/SwissFEL+test/')'
# equals to: elog.open('elog-gfa', 'SwissFEL test', user='uname', pasword='pass')  # defaults: use-ssl=True, port=443 (for ssl)
```

Once elog object is created one of its public methods can be used to read, create, reply to, edit or delete the message.
- read:
```python
# Read message with with message ID = 23
message, attributes, attachments = my_logbook.read_msg(23)
```
- create:
```python
# Create new message with some text, attributes (dict of attributes + kwargs) and attachments
new_msg_id = my_logbook.post_msg('This is message text', attributes=dict_of_attributes, attachments=list_of_attachments, attribute_as_param='value')
```
- reply to:
```python
# Reply to message with ID=23
new_msg_id = my_logbook.post_msg('This is a reply', msg_id=23, reply=True, attributes=dict_of_attributes, attachments=list_of_attachments, attribute_as_param='value')
```
- edit:
```python
# Edit message with ID=23. Changed message text, some attributes (dict of edited attributes + kwargs) and new attachments
edited_msg_id = my_logbook.post_msg('This is new message text', msg_id=23, attributes=dict_of_changed_attributes, attachments=list_of_new_attachments, attribute_as_param='new value')
```
- delete (message and all its replies):
```python
# Delete message with ID=23. All its replies will also be deleted.
my_logbook.delete_msg_thread(23)
```

# Methods
## elog.open()
```python
elog.open(hostname, logbook='', port=None, user=None, password=None, subdir='', use_ssl=True, encrypt_pwd=True))
```
Creates a new logbook object.

**hostname**: elog server hostname. If whole url is specified here, it will be parsed and arguments: "logbook, port, subdir, use_ssl" will be overwritten by parsed values.

**logbook**: name of the logbook on the elog server

**port**: elog server port (if not specified will default to '80' if ```use_ssl=False``` or '443' if ```use_ssl=True```

**user**: user name (if authentication needed)

**password**: password (if authentication needed). Password will be encrypted with sha256, unless ```encrypt_pwd=False``` (default: True).

**subdir**: subdirectory of logbooks locations

**use_ssl**: connect using ssl?

**encrypt_pwd**: To avoid exposing password in the code, this flag can be set to ```False``` and password will then be used as it is (user needs to provide sha256 encrypted password with ```salt= ''``` and ```rounds = 5000```)

-----------------------------------
**return**: Logbook() object.

## logbook.read_msg()
```python
read_msg(msg_id)
```
Reads message from the logbook server and returns tuple of (message, attributes, attachments) where:

- message: string with message body

- attributes: dictionary of all attributes returned by the logbook

- attachments: list of urls to attachments on the logbook server

**msg_id**: ID number of message to be read from the logbook.

-----------------------------------------------
**return**: message, attributes, attachments


## logbook.post_msg()
```python
post_msg(message, msg_id=None, reply=False, attributes=None, attachments=None, encoding='plain', **kwargs)
```

Posts message to the logbook. If msg_id is not specified new message will be created, otherwise existing message will be edited, or a reply (if reply=True) to it will be created. This method returns the msg_id of the newly created/edited message.

**message**: string with message text

**msg_id**: ID number of message to edit or reply. If not specified new message is created.

**reply**: If 'True' reply to existing message is created instead of editing it

**attributes**: Dictionary of attributes. Following attributes are used internally by the elog and will be ignored: Text, Date, Encoding, Reply to, In reply to, Locked by, Attachment

**attachments**: list of:

 - file like objects which read() will return bytes (if file_like_object.name is not defined, default name "attachment<i>" will be used.

 - paths to the files
 All items will be appended as attachment to the elog entry. In case of unknown attachment an exception ```LogbookInvalidAttachment``` will be raised.

**encoding**: Defines encoding of the message. Can be: 'plain' -> plain text, 'html'->html-text, 'ELCode' --> elog formatting syntax

**kwargs**: Anything in the kwargs will be interpreted as attribute. e.g.: logbook.post_msg('Test text', Author='Name'), "Author" will be sent as an attribute. If named same as one of the
attributes defined in "attributes", kwargs will have priority.

------------------------- 
**return**: msg_id

## logbook.delete_msg_thread()

```python
delete_msg_thread(msg_id)
```
Deletes message thread (!!!message + all replies!!!) from logbook. It also deletes all attachments of deleted messages from the server.

**msg_id**: message to be deleted

# Exceptions
elog module can throw following exceptions.

```
LogbookError
    LogbookAuthenticationError
    LogbookMessageRejected
        LogbookInvalidAttachmentType
        LogbookInvalidMessageID
    LogbookServerProblem
```

## LogbookError

Parent class for logbook exception.

### LogbookAuthenticationError

Raised when there is a problem with user name or password.

### LogbookMessageRejected
Raised when manipulating/creating message was rejected by the server or there was problem composing message.

#### LogbookInvalidAttachmentType
Raised when passed attachment has invalid type (not file like object or path to the file).

#### LogbookInvalidMessageID
Raised when there is no message with specified ID on the server.

### LogbookServerProblem
Raised when problem accessing logbook server.


# Installation
Elog module depends on ```passlib``` library used for password encryption. It is packed as anaconda package and can be installed as any other anaconda package.

# Authors 

- Rok Vintar (rok.vintar@cosylab.com)