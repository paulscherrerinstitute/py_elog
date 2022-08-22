[![conda_publish](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/conda_publish.yaml/badge.svg)](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/conda_publish.yaml)
[![pypi_publish](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/pypi_publish.yaml/badge.svg)](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/pypi_publish.yaml)
[![python_test](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/python_test.yaml/badge.svg)](https://github.com/paulscherrerinstitute/py_elog/actions/workflows/python_test.yaml)

# Overview
This Python module provides a native interface [electronic logbooks](https://midas.psi.ch/elog/). It is compatible with Python versions 3.5 and higher.

# Usage

For accessing a logbook at ```http[s]://<hostename>:<port>/[<subdir>/]<logbook>/[<msg_id>]``` a logbook handle must be retrieved.

```python
import elog

# Open GFA SwissFEL test logbook
logbook = elog.open('https://elog-gfa.psi.ch/SwissFEL+test/')

# Contstructor using detailed arguments
# Open demo logbook on local host: http://localhost:8080/demo/
logbook = elog.open('localhost', 'demo', port=8080, use_ssl=False)
```

Once you have hold of the logbook handle one of its public methods can be used to read, create, reply to, edit or delete the message.

## Get Existing Message Ids
Get all the existing message ids of a logbook

```python
message_ids = logbook.get_message_ids()
```

To get if of the last inserted message
```python
last_message_id = logbook.get_last_message_id()
```

## Read Message

```python
# Read message with with message ID = 23
message, attributes, attachments = logbook.read(23)
```

## Create Message

```python
# Create new message with some text, attributes (dict of attributes + kwargs) and attachments
new_msg_id = logbook.post('This is message text', attributes=dict_of_attributes, attachments=list_of_attachments, attribute_as_param='value')
```
 
What attributes are required is determined by the configuration of the elog server (keywork `Required Attributes`).
If the configuration looks like this:
 
```
Required Attributes = Author, Type
```
 
You have to provide author and type when posting a message.
 
In case type need to be specified, the supported keywords can as well be found in the elog configuration with the key `Options Type`.
 
If the config looks like this:
```
Options Type = Routine, Software Installation, Problem Fixed, Configuration, Other
```

A working create call would look like this:

```python
new_msg_id = logbook.post('This is message text', author='me', type='Routine')
```

 

## Reply to Message

```python
# Reply to message with ID=23
new_msg_id = logbook.post('This is a reply', msg_id=23, reply=True, attributes=dict_of_attributes, attachments=list_of_attachments, attribute_as_param='value')
```

## Edit Message

```python
# Edit message with ID=23. Changed message text, some attributes (dict of edited attributes + kwargs) and new attachments
edited_msg_id = logbook.post('This is new message text', msg_id=23, attributes=dict_of_changed_attributes, attachments=list_of_new_attachments, attribute_as_param='new value')
```

## Search Messages

```python
# Search for text in messages or specify attributes for search, returns list of message ids
logbook.search('Hello World')
logbook.search('Hello World', n_results=20, scope='attribname')
logbook.search({'attribname' : 'Hello World', ... })
```

## Delete Message (and all its replies)

```python
# Delete message with ID=23. All its replies will also be deleted.
logbook.delete(23)
```

__Note:__ Due to the way elog implements delete this function is only supported on english logbooks.

# Installation
The Elog module and only depends on the `passlib` and `requests` library used for password encryption and http(s) communication. It is packed as [anaconda package](https://anaconda.org/paulscherrerinstitute/elog) and can be installed as follows:

```bash
conda install -c paulscherrerinstitute elog
```
