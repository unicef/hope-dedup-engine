from constance import config

from hope_dedup_engine.apps.faces.managers.net import DNNInferenceManager


def test_successful(mock_storage_manager, mock_net_manager):
    dnn_manager = DNNInferenceManager(mock_storage_manager.storages["cv2dnn"])
    mock_net_manager.setPreferableBackend.assert_called_once_with(int(config.DNN_BACKEND))
    mock_net_manager.setPreferableTarget.assert_called_once_with(int(config.DNN_TARGET))

    assert isinstance(dnn_manager, DNNInferenceManager)
    assert dnn_manager.get_model() == mock_net_manager
