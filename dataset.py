"""
Preprocesses MIDI files
"""
import os
import math
import numpy as np
import torch
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset

import numpy
import math
import random
from tqdm import tqdm
import multiprocessing
import itertools

import midi_io
from util import *
import constants as const

class MusicDataset(Dataset):
    def __init__(self, file_ids, data_files):
        """    
        Loads all MIDI files from provided files.
        """
        self.seqs = []
        self.seq_ids = []
        ignore_count = 0
        
        for f in tqdm(data_files):
            try:
                # Cache encoding
                cache_path = os.path.join(CACHE_DIR, f + '.tokenized.npy')
                try:
                    seq = np.load(cache_path)
                except:
                    seq = midi_io.load_midi(f)
                    seq = [const.TOKEN_EOS] + seq + [const.TOKEN_EOS]
                    seq = np.array(seq, dtype='int64')

                    # Perform caching
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    np.save(cache_path, seq)

                self.seq_ids.append(file_ids.index(f))
                self.seqs.append(seq)
            except Exception as e:
                print('Unable to load {}'.format(f), e)
                ignore_count += 1

        print('{} files ignored.'.format(ignore_count))
        print('Loaded {} MIDI file(s) with average length {}'.format(len(self.seqs), sum(len(s) for s in self.seqs) / len(self.seqs)))

    def __len__(self):
        return len(self.seqs) * RANDOM_TRANSPOSE

    def __getitem__(self, idx):
        idx = idx // RANDOM_TRANSPOSE
        seq = self.seqs[idx]
        seq_id = self.seq_ids[idx]

        # Random subsequence
        start_index = random.randint(0, len(seq) - 1 - const.SEQ_LEN)
        seq = seq[start_index:start_index+const.SEQ_LEN]

        # Random transposition
        seq = transpose(seq)
        return torch.LongTensor(list(seq)), torch.tensor(seq_id)
            
def transpose(sequence, amount=RANDOM_TRANSPOSE):
    """ A generator that represents the sequence. """
    # Transpose by *amount* semitones at most
    transpose = random.randint(-amount, amount)

    if transpose == 0:
        return sequence

    # Perform transposition (consider only notes)
    return (min(max(evt + transpose, TOKEN_NOTE), TOKEN_VEL) if evt >= TOKEN_NOTE and evt < TOKEN_VEL else evt for evt in sequence)

def get_tv_loaders(args):
    data_files = get_all_files([const.DATA_FOLDER])
    data_files = sorted(data_files)
    train_files, val_files = validation_split(data_files)
    print('Training Files:', len(train_files), 'Validation Files:', len(val_files))
    return get_loader(args, data_files, train_files), get_loader(args, data_files, val_files)

def get_loader(args, file_ids, files):
    print('Setup dataset...')
    ds = MusicDataset(file_ids, files)
    print('Done.')
    return torch.utils.data.DataLoader(
        dataset=ds, 
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=1,
        drop_last=True
    )

def validation_split(seqs, split=0.2):
    """
    Splits the data iteration list into training and validation indices
    """
    # Shuffle sequences randomly
    r = list(range(len(seqs)))
    random.shuffle(r)

    num_val = int(math.ceil(len(r) * split))
    train_indicies = r[:-num_val]
    val_indicies = r[-num_val:]

    assert len(val_indicies) == num_val
    assert len(train_indicies) == len(r) - num_val

    train_seqs = [seqs[i] for i in train_indicies]
    val_seqs = [seqs[i] for i in val_indicies]

    return train_seqs, val_seqs
