import os
import h5py
import z5py
import numpy as np

from skimage.transform import resize
from elf.segmentation.utils import normalize_input

PATH = '/g/rompani/lgn-em-datasets/data/0.0.0/images/local/sbem-adult-1-lgn-raw.n5'
BOUTON_PATH = '/g/rompani/lgn-em-datasets/data/0.0.0/images/local/sbem-adult-1-lgn-boutons.n5'
MODEL_PATH = os.path.join('/g/kreshuk/pape/Work/my_projects/super_embeddings/experiments/lgn/models_unsupervised-3d',
                          'lr0.0001_use-affs1_weight1.state')

CENTER = (338.21969826291144, 115.66693588888701, 33.773648522038826)


def run_prediction(raw):
    from mipnet.models.unet import AnisotropicUNet
    from mipnet.utils.prediction import predict_with_halo
    scale_factors = [
        [1, 2, 2], [1, 2, 2], [2, 2, 2], [2, 2, 2]
    ]
    model_kwargs = dict(scale_factors=scale_factors,
                        in_channels=1, out_channels=12,
                        initial_features=32, gain=2,
                        pad_convs=True)
    ckpt = (
        AnisotropicUNet,
        model_kwargs,
        MODEL_PATH,
        'model'
    )

    block_shape = (32, 256, 256)
    halo = (8, 64, 64)
    outer_block_shape = tuple(bs + 2 * ha for bs, ha in zip(block_shape, halo))

    def preprocess(inp):
        inp = normalize_input(inp)
        return inp

    gpus = [0]
    pred = predict_with_halo(raw, ckpt, gpus=gpus, inner_block_shape=block_shape,
                             outer_block_shape=outer_block_shape, preprocess=preprocess)
    pred = np.max(pred[:4], axis=0)
    pred = normalize_input(pred)
    return pred


def make_test_data(halo=[64, 512, 512]):
    resolution = [.04, .01, .01]
    with z5py.File(PATH, 'r') as f:
        ds = f['setup0/timepoint0/s0']

        center = [int(ce / res) for ce, res in zip(CENTER[::-1], resolution)]
        bb = tuple(slice(ce - ha, ce + ha) for ce, ha in zip(center, halo))
        raw = ds[bb]

    # to get rid of some ugly artifact
    raw = raw[:100]
    pred = run_prediction(raw)

    with h5py.File('./test_data.h5', 'a') as f:
        f.create_dataset('raw', data=raw, compression='gzip')
        f.create_dataset('boundaries', data=pred, compression='gzip')


def add_boutons(scale_factor=[1, 2, 2], halo=[64, 512, 512]):
    resolution = [.04, .02, .02]
    with z5py.File(BOUTON_PATH, 'r') as f:
        ds = f['setup0/timepoint0/s0']

        center = [int(ce / res) for ce, res in zip(CENTER[::-1], resolution)]
        bb = tuple(slice(ce - ha // sf, ce + ha // sf)
                   for ce, ha, sf in zip(center, halo, scale_factor))
        seg = ds[bb]

    seg = seg[:100]
    target_shape = tuple(sh * sf for sh, sf in zip(seg.shape, scale_factor))
    seg = resize(seg, target_shape, order=0, preserve_range=True).astype(seg.dtype)

    with h5py.File('./test_data.h5', 'a') as f:
        f.create_dataset('boutons', data=seg, compression='gzip')


def check_test_data():
    import napari
    with h5py.File('./test_data.h5', 'r') as f:
        raw = f['raw'][:]
        bd = f['boundaries'][:]
        boutons = f['boutons'][:]

    with napari.gui_qt():
        viewer = napari.Viewer()
        viewer.add_image(raw)
        viewer.add_image(bd)
        viewer.add_labels(boutons)


def replace_defect():
    zz = [66, 67, 68]
    with h5py.File('./test_data.h5', 'a') as f:
        for z in zz:
            for name in ('raw', 'boundaries', 'boutons'):
                ds = f[name]
                ds[z] = ds[z - 1]


if __name__ == '__main__':
    make_test_data()
    add_boutons()
    replace_defect()

    # check_test_data()
