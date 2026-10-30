import os, soundfile as sf
path = r'E:\EvalWork\noisy_samples\acl_2022.acl-long.110_OOFFICE_0dB.wav'
print('Exists?', os.path.exists(path))
if os.path.exists(path):
    data, sr = sf.read(path)
    print('Sample rate:', sr)
    print('Duration (s):', len(data)/sr)
