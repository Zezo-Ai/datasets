import os
import time
import uuid
from contextlib import contextmanager
from typing import Optional

import pytest
import requests
from huggingface_hub.hf_api import HfApi, RepositoryNotFoundError
from huggingface_hub.utils import hf_raise_for_status
from huggingface_hub.utils._headers import _http_user_agent


CI_HUB_USER = "__DUMMY_TRANSFORMERS_USER__"
CI_HUB_USER_FULL_NAME = "Dummy User"
CI_HUB_USER_TOKEN = "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"

CI_HUB_ENDPOINT = "https://hub-ci.huggingface.co"
CI_HUB_DATASETS_URL = CI_HUB_ENDPOINT + "/datasets/{repo_id}/resolve/{revision}/{path}"
CI_HFH_HUGGINGFACE_CO_URL_TEMPLATE = CI_HUB_ENDPOINT + "/{repo_id}/resolve/{revision}/{filename}"


@pytest.fixture
def ci_hub_config(monkeypatch):
    monkeypatch.setattr("datasets.config.HF_ENDPOINT", CI_HUB_ENDPOINT)
    monkeypatch.setattr("datasets.config.HUB_DATASETS_URL", CI_HUB_DATASETS_URL)
    monkeypatch.setattr(
        "huggingface_hub.file_download.HUGGINGFACE_CO_URL_TEMPLATE", CI_HFH_HUGGINGFACE_CO_URL_TEMPLATE
    )
    old_environ = dict(os.environ)
    os.environ["HF_ENDPOINT"] = CI_HUB_ENDPOINT
    yield
    os.environ.clear()
    os.environ.update(old_environ)


@pytest.fixture
def set_ci_hub_access_token(ci_hub_config, monkeypatch):
    # Enable implicit token
    monkeypatch.setattr("huggingface_hub.constants.HF_HUB_DISABLE_IMPLICIT_TOKEN", False)
    old_environ = dict(os.environ)
    os.environ["HF_TOKEN"] = CI_HUB_USER_TOKEN
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "0"
    yield
    os.environ.clear()
    os.environ.update(old_environ)


def _http_ci_user_agent(*args, **kwargs):
    ua = _http_user_agent(*args, **kwargs)
    return ua + os.environ.get("CI_HEADERS", "")


@pytest.fixture(autouse=True)
def set_hf_ci_headers(monkeypatch):
    old_environ = dict(os.environ)
    os.environ["TRANSFORMERS_IS_CI"] = "1"
    monkeypatch.setattr("huggingface_hub.utils._headers._http_user_agent", _http_ci_user_agent)
    yield
    os.environ.clear()
    os.environ.update(old_environ)


@pytest.fixture(scope="session")
def hf_api():
    return HfApi(endpoint=CI_HUB_ENDPOINT)


@pytest.fixture(scope="session")
def hf_token():
    yield CI_HUB_USER_TOKEN


@pytest.fixture
def cleanup_repo(hf_api):
    def _cleanup_repo(repo_id):
        hf_api.delete_repo(repo_id, token=CI_HUB_USER_TOKEN, repo_type="dataset")

    return _cleanup_repo


@pytest.fixture
def temporary_repo(cleanup_repo):
    @contextmanager
    def _temporary_repo(repo_id: Optional[str] = None):
        repo_id = repo_id or f"{CI_HUB_USER}/test-dataset-{uuid.uuid4().hex[:6]}-{int(time.time() * 10e3)}"
        try:
            yield repo_id
        finally:
            try:
                cleanup_repo(repo_id)
            except RepositoryNotFoundError:
                pass

    return _temporary_repo


@pytest.fixture(scope="session")
def _hf_gated_dataset_repo_txt_data(hf_api: HfApi, hf_token, text_file_content):
    repo_name = f"repo_txt_data-{int(time.time() * 10e6)}"
    repo_id = f"{CI_HUB_USER}/{repo_name}"
    hf_api.create_repo(repo_id, token=hf_token, repo_type="dataset")
    hf_api.upload_file(
        token=hf_token,
        path_or_fileobj=text_file_content.encode(),
        path_in_repo="data/text_data.txt",
        repo_id=repo_id,
        repo_type="dataset",
    )
    path = f"{hf_api.endpoint}/api/datasets/{repo_id}/settings"
    repo_settings = {"gated": "auto"}
    r = requests.put(
        path,
        headers={"authorization": f"Bearer {hf_token}"},
        json=repo_settings,
    )
    hf_raise_for_status(r)
    yield repo_id
    try:
        hf_api.delete_repo(repo_id, token=hf_token, repo_type="dataset")
    except (requests.exceptions.HTTPError, ValueError):  # catch http error and token invalid error
        pass


@pytest.fixture()
def hf_gated_dataset_repo_txt_data(_hf_gated_dataset_repo_txt_data, ci_hub_config):
    return _hf_gated_dataset_repo_txt_data


@pytest.fixture(scope="session")
def hf_private_dataset_repo_txt_data_(hf_api: HfApi, hf_token, text_file_content):
    repo_name = f"repo_txt_data-{int(time.time() * 10e6)}"
    repo_id = f"{CI_HUB_USER}/{repo_name}"
    hf_api.create_repo(repo_id, token=hf_token, repo_type="dataset", private=True)
    hf_api.upload_file(
        token=hf_token,
        path_or_fileobj=text_file_content.encode(),
        path_in_repo="data/text_data.txt",
        repo_id=repo_id,
        repo_type="dataset",
    )
    yield repo_id
    try:
        hf_api.delete_repo(repo_id, token=hf_token, repo_type="dataset")
    except (requests.exceptions.HTTPError, ValueError):  # catch http error and token invalid error
        pass


@pytest.fixture()
def hf_private_dataset_repo_txt_data(hf_private_dataset_repo_txt_data_, ci_hub_config):
    return hf_private_dataset_repo_txt_data_


@pytest.fixture(scope="session")
def hf_private_dataset_repo_zipped_txt_data_(hf_api: HfApi, hf_token, zip_csv_with_dir_path):
    repo_name = f"repo_zipped_txt_data-{int(time.time() * 10e6)}"
    repo_id = f"{CI_HUB_USER}/{repo_name}"
    hf_api.create_repo(repo_id, token=hf_token, repo_type="dataset", private=True)
    hf_api.upload_file(
        token=hf_token,
        path_or_fileobj=str(zip_csv_with_dir_path),
        path_in_repo="data.zip",
        repo_id=repo_id,
        repo_type="dataset",
    )
    yield repo_id
    try:
        hf_api.delete_repo(repo_id, token=hf_token, repo_type="dataset")
    except (requests.exceptions.HTTPError, ValueError):  # catch http error and token invalid error
        pass


@pytest.fixture()
def hf_private_dataset_repo_zipped_txt_data(hf_private_dataset_repo_zipped_txt_data_, ci_hub_config):
    return hf_private_dataset_repo_zipped_txt_data_


@pytest.fixture(scope="session")
def hf_private_dataset_repo_zipped_img_data_(hf_api: HfApi, hf_token, zip_image_path):
    repo_name = f"repo_zipped_img_data-{int(time.time() * 10e6)}"
    repo_id = f"{CI_HUB_USER}/{repo_name}"
    hf_api.create_repo(repo_id, token=hf_token, repo_type="dataset", private=True)
    hf_api.upload_file(
        token=hf_token,
        path_or_fileobj=str(zip_image_path),
        path_in_repo="data.zip",
        repo_id=repo_id,
        repo_type="dataset",
    )
    yield repo_id
    try:
        hf_api.delete_repo(repo_id, token=hf_token, repo_type="dataset")
    except (requests.exceptions.HTTPError, ValueError):  # catch http error and token invalid error
        pass


@pytest.fixture()
def hf_private_dataset_repo_zipped_img_data(hf_private_dataset_repo_zipped_img_data_, ci_hub_config):
    return hf_private_dataset_repo_zipped_img_data_
