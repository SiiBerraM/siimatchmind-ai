import os
from huggingface_hub import HfApi
HfApi().upload_file(path_or_fileobj='dist/SiiMatchMind-standalone.html', path_in_repo='index.html', repo_id='Siiberra/siimatchmind-ai', repo_type='space', token=os.environ['HF_TOKEN'])
