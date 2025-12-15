import os
import cascade as cs
from cascade.spec.file import File

def test_file_read_write_text(tmp_path):
    p = tmp_path / "hello.txt"
    f = File(str(p))

    # Test Write (should create parent dir if mostly empty, but here tmp_path exists)
    f.write_text("Hello World")
    assert p.read_text() == "Hello World"

    # Test Read
    assert f.read_text() == "Hello World"

def test_file_auto_makedirs(tmp_path):
    # Test that write operations create nested directories
    nested_path = tmp_path / "sub" / "dir" / "data.txt"
    f = File(str(nested_path))
    
    f.write_text("nested content")
    
    assert nested_path.exists()
    assert f.read_text() == "nested content"

def test_file_read_write_bytes(tmp_path):
    p = tmp_path / "data.bin"
    f = File(str(p))

    data = b"\x00\x01\x02"
    f.write_bytes(data)
    assert p.read_bytes() == data
    assert f.read_bytes() == data

def test_file_exists(tmp_path):
    p = tmp_path / "exist.txt"
    f = File(str(p))
    assert not f.exists()
    
    p.touch()
    assert f.exists()

def test_file_str_repr(tmp_path):
    f = File("my/path")
    assert str(f) == "my/path"
    assert repr(f) == "File('my/path')"
    
def test_file_integration_with_task(tmp_path):
    """
    Ensures that File objects can be passed through tasks seamlessly.
    """
    target = tmp_path / "config.json"
    target.write_text('{"foo": "bar"}')
    
    @cs.task
    def read_config(f: File) -> str:
        # Verify we received a File object and can use it
        assert isinstance(f, File)
        return f.read_text()
        
    file_obj = File(str(target))
    # Pass File object as argument
    task_res = read_config(file_obj)
    
    res = cs.run(task_res)
    assert res == '{"foo": "bar"}'