# Overview
This python module provides a python interface to [electronic logbooks](https://midas.psi.ch/elog/) for python versions 3.5 and higher.

# Quick startup
This section provides a simple example. For detailed information about specific methods, please consult section TODO.

Once elog module is installed (seeTODO) it can be imported with ```import elog```. To start working with logbook, its instance must be opened using
function ```elog.open(hostname, logbook, port=None, user=None, password=None, subdir='', use_ssl=True, encrypt_pwd=True)```. Parameters needed by the open can be
determined from logbook's url: http://<logbook>:<port>/[<subdir>/]<logbook>/[<msg_id>]. For example, logbook 'demo' running on localhost logbook can be opened with:
 
```python
import elog

my_logbook = elog.open('localhost', 'demo', port=8080, use_ssl=False)
```
Function ```open()``` returns a Logbook() object which has methods to read, write ore delete logbook messages.

To read a message with ID=5 use ```read_msg``` as follows
'''python
message, attributes, attachments = my_logbook.read_msg(5)
'''
Returned parameters are body *message*, dictionary of all *attributes* and list of urls to existing *attachments*.

To write a new one, edit existing message, or just ti reply to it ```post_msg``` should be used. Following example explains howt to create a new message, make a reply on it and change the its content.
```python
msg_1_id = my_logbook.post_msg('Hello world', attributes={'Attribute_1': 'Test'}, attachments=['/path/to/my/file.txt', file_like_obj], Attribute_as_arg = 'Test2')

msg_2_id = my_logbook.post_msg('Reply to first one.', msg_id = msg_1_id, reply=True, Attribute_1='Test3')

msg_1_id = my_logbook.post_msg('Hello world', attributes={'Attribute_1': 'Test'}, attachments=['/path/to/my/file.txt', file_like_obj], Attribute_as_arg = 'Test2')
msg_1_id = my_logbook.post_msg('Edited message', msg_id=msg_1_id, Attribute_1 = 'Edited')

```



# Authors 

- Rok Vintar (rok.vintar@cosylab.com)