def test_strip_master():
    from cheeseprism.utils import strip_master
    assert strip_master('wat-10.1-master.tar.gz') == 'wat-10.1.tar.gz'
    assert strip_master('wat-10.1.tar.gz') == 'wat-10.1.tar.gz' 
