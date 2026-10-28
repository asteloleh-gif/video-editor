import hashlib
import pytest
from video_editor.story_pilot import align_scenes, contained, validate_assets


def test_source_integrity_and_license_are_checked_before_render(tmp_path):
    media=tmp_path/'source.jpg';media.write_bytes(b'original')
    asset={'id':'photo','kind':'image','raw':media.name,'source':'https://commons.wikimedia.org/wiki/File:source.jpg','author':'Author','reason':'Reviewed scene match','license':'CC-BY-4.0','sha256':hashlib.sha256(b'original').hexdigest()}
    brief={'assets':[asset],'scenes':[{'asset':'photo'}]*7}
    validate_assets(brief,tmp_path)
    media.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):validate_assets(brief,tmp_path)
    asset['license']='UNKNOWN'
    with pytest.raises(ValueError,match='reviewed'):validate_assets(brief,tmp_path)


def test_raw_media_must_stay_inside_declared_folder(tmp_path):
    with pytest.raises(ValueError,match='leaves'):contained(tmp_path,'../other.wav')


def test_scenes_follow_spoken_anchors_and_missing_anchors_stop_the_build():
    scenes=[{'id':'intro','anchor':[]},{'id':'middle','anchor':['actual words']}]
    segments=[{'start':0,'end':1,'text':'Intro'},{'start':1.5,'end':3,'text':'Actual words.'}]
    result=align_scenes(scenes,segments,4)
    assert [(s['start'],s['end']) for s in result]==[(0,1.5),(1.5,4)]
    with pytest.raises(ValueError,match='No verified'):align_scenes(scenes,segments[:1],4)


def test_scene_boundaries_cannot_overlap():
    scenes=[{'id':'intro','anchor':[]},{'id':'second','anchor':['same']}]
    with pytest.raises(ValueError,match='overlap'):align_scenes(scenes,[{'start':0,'end':1,'text':'same'}],2)
