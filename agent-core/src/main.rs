//! Optional asynchronous JSON-lines protocol validator. No subprocess execution.
use serde_json::{json, Value};
use tokio::io::{self, AsyncBufReadExt, AsyncWriteExt, BufReader};
#[tokio::main(flavor = "current_thread")]
async fn main() -> io::Result<()> {
    let mut input = BufReader::new(io::stdin());
    let mut output = io::stdout();
    loop {
        let mut line = Vec::new();
        // Read in bounded chunks so malformed input cannot exhaust the VPS.
        loop {
            let buffer = input.fill_buf().await?;
            if buffer.is_empty() { break; }
            let used = buffer.iter().position(|b| *b == b'\n').map_or(buffer.len(), |p| p + 1);
            if line.len() + used > 1_048_576 { return Err(io::Error::new(io::ErrorKind::InvalidData, "request too large")); }
            line.extend_from_slice(&buffer[..used]);
            input.consume(used);
            if line.last() == Some(&b'\n') { break; }
        }
        if line.is_empty() { break; }
        let reply = match serde_json::from_slice::<Value>(&line) {
            Ok(value) => json!({"valid": value.is_object() && value.get("method").and_then(Value::as_str).is_some(), "id": value.get("id")}),
            Err(_) => json!({"valid": false, "error": "invalid JSON"}),
        };
        output.write_all(reply.to_string().as_bytes()).await?;
        output.write_all(b"\n").await?;
        output.flush().await?;
    }
    Ok(())
}
