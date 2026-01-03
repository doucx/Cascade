use pyo3.prelude::*;
use pyo3.types::{PyDict, PyAny};

/// A minimal Rust implementation of the Cascade Reactor.
#[pyclass]
struct RustReactor {
    active_task_count: usize,
}

#[pymethods]
impl RustReactor {
    #[new]
    fn new(
        _graph: &PyAny,
        _memory: &PyAny,
        _executor: &PyAny,
        _function_map: &PyDict,
        _resource_registry: &PyAny,
    ) -> Self {
        println!("RustReactor: Initialized via FFI!");
        RustReactor {
            active_task_count: 0,
        }
    }

    #[getter]
    fn active_task_count(&self) -> usize {
        self.active_task_count
    }

    fn prime(&self) {
        println!("RustReactor: prime() called (noop)");
    }

    fn step<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        // Return a future that resolves to 0 (tasks fired)
        pyo3_asyncio::tokio::future_into_py(py, async {
            println!("RustReactor: step() called (async noop)");
            Ok(0)
        })
    }

    fn add_sink(&self, _node_id: String, _port_name: String, _callback: PyObject) {
        println!("RustReactor: add_sink() called (noop)");
    }
}

/// The module definition.
#[pymodule]
fn cascade_vm_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RustReactor>()?;
    Ok(())
}