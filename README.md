# Gofile.py: Python API wrapper for Gofile.io

Python API wrapper for Gofile.io with extensive features such as uploading/downloading bulk files/folders

## Usage

```python
    from gofile import Gofile
    g = Gofile(token=user_token)
    
    g.download_folder(url="https://gofile.io/example_link",default_path="/path/to/the/desired/folder")

    >> [...]

    g.upload("path/to/the/folder/to/be/uploaded/",folder_id="example_folder_content_id")

    >> [{'downloadPage':'link_to_file',...}]

    g.create_folder("Test","target_folder_id")

    >> {'id':'new_folderid','type':'folder','name':'Test'...}
```

_Don't know user token? No problem!_

```python
    from gofile import Gofile
    g = Gofile(email="example@example.com")

    g.create_folder("Test","target_folder_id")

    >> "Please check your email (spam box as well) and paste the link here: " #after it's pasted it's going to execute the rest of the code

    >> {'id':'new_folderid','type':'folder','name':'Test'...}

```

