use pyo3::prelude::*;
use pyo3::types::PyDict;

/// A minimal Rust implementation of the Cascade Reactor using PyO3 0.23 Bound API.
#[pyclass]
struct RustReactor {
    #[pyo3(get)]
    active_task_count: usize,
}

#[pymethods]
impl RustReactor {
    #[new]
    fn new(
        _graph: Bound<'_, PyAny>,
        _memory: Bound<'_, PyAny>,
        _executor: Bound<'_, PyAny>,
        _function_map: Bound<'_, PyDict>,
        _resource_registry: Bound<'_, PyAny>,
    ) -> Self {
        println!("RustReactor: Initialized via FFI (PyO3 0.23, Python 3.13 confirmed)!");
        RustReactor {
            active_task_count: 0,
        }
    }

    fn prime(&self) {
        println!("RustReactor: prime() called (noop)");
    }

    fn step<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        // Since we removed pyo3-asyncio for compatibility, we'll manually create
        // a completed Python Future to keep the EventDrivenRunner's await logic happy.
        let asyncio = py.import("asyncio")?;
        let loop_ = asyncio.call_method0("get_event_loop")?;
        let future = loop_.call_method0("create_future")?;
        
        // Return 0 tasks fired
        future.call_method1("set_result", (0,))?;
        
        println!("RustReactor: step() called (returning manual future)");
        Ok(future)
    }

    fn add_sink(&self, _node_id: String, _port_name: String, _callback: PyObject) {
        println!("RustReactor: add_sink() called (noop)");
    }
}

/// The module definition.
#[pymodule]
fn cascade_vm_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustReactor>()?;
    Ok(())
}