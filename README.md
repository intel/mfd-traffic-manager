> [!IMPORTANT]  
> This project is under development. All source code and features on the main branch are for the purpose of testing or evaluation and not production ready.

# MFD Traffic Manager

Module for handling variety of types of traffic under one consistent API.


## Class Diagram

```mermaid
classDiagram
    class Traffic{
        +start()
        +stop()
        +run()
        +validate()
    }
    class Stream{
        +str name
        +List[Traffic] clients
        +Traffic Server
        +List[Traffic] all_traffics
        +start()
        +stop()
        +run(int duration)
        +validate(criteria)

    }
    class TrafficManager{
        +List[Stream] streams
        +start(str name)
        +stop(str name)
        +run(str name, int duration)
        +start_all()
        +stop_all()
        +validate_all(criteria)
        +validate(name, criteria)
        +add_stream(Stream stream)

    }
    class IperfTraffic{
        ...
    }
    class Iperf2ClientTraffic{
        ...
    }
    class Iperf2ServerTraffic{
        ...
    }
    class Iperf3ClientTraffic{
        ...
    }
    class Iperf3ServerTraffic{
        ...
    }
    TrafficManager *-- Stream
    Stream *-- Traffic
    IperfTraffic --|> Traffic
    Iperf2ClientTraffic --|> IperfTraffic
    Iperf2ServerTraffic --|> IperfTraffic
    Iperf3ClientTraffic --|> IperfTraffic
    Iperf3ServerTraffic --|> IperfTraffic
```

## Usage

### `Traffic` API
All classes for specific traffics (e.g. Iperf2Traffic) should inherit from Traffic base class interface.
It provides some abstract methods, all of them need to be implemented in child classes:
* `start() -> None` - start traffic indefinitely
* `stop() -> None` - stop traffic
* `run(duration: int) -> None` - run traffic for a specified number of seconds (usually for server, process should be running until stop)
* `validate(validation_criteria: Optional[Dict[Callable, Dict[str, Any]]]) -> bool` - validate traffic by passed criteria

### `Stream` API
Represents single stream of the traffic (collection of server and clients instances).

* constructor `(clients: List["Traffic"], server: "Traffic", name: Optional[str] = "Stream", port: Optional[int] = None, port_find_tries: int = 10)`
* `start(delay: Optional[int]) -> None` - start all traffics (first server, then clients)
* `stop(delay: Optional[int]) -> None` - stop all traffics (first clients, then server)
* `run(duration: int) -> None` - run all traffics for a specific time (first server, then clients)
* `validate(common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  *,
  server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,) -> bool` - validate all traffics

Stream has optional `port` argument. If `port` is provided stream will reserve passed port, or found free port
trying `port_find_tries` times with incrementation. After stopping stream port will be unreserved automatically.
`Port` argument will override `port` value of server and client `Traffic` objects.

### `SingleHostStream` API

Represents a single stream of the traffic, where only server is used (e.g., ping, ix_chariot)

* constructor `(server: "Traffic", name: Optional[str] = "Stream", port: Optional[int] = None, port_find_tries: int = 10)`
* `validate(common_validation_criteria: dict[Callable, dict[str, Any]]] | None = None) - validate all traffics

### `TrafficManager` API
Represent class for managing streams (collection of traffics).

* `start_all() -> None` - start all streams
* `stop_all() -> None` - stop all streams
* `run_all(duration: int) -> None` - run all streams for a specific time
* `validate_all(common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  *,
  server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,) -> bool` - validate all streams
* `start(name: str, delay: Optional[int]) -> None` - start stream by name
* `stop(name: str, delay: Optional[int]) -> None` - stop stream by name
* `run(name: str, duration: int) -> None` - run stream by name for a specific time
* `validate(name: str, common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  *,
  server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
  clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,) -> bool` - validate stream by name

### Utils API

#### Port reservation

* `check_if_port_is_free(connection: "AsyncConnection", port: int)` - check if port is ready to use
* `reserve_port(connection: "AsyncConnection", port: int, find_port: bool = True, count: int = 10) -> PortReservation:` -
  reserve given port in system, using find_port flag API will find first free port, count is related to how many times
  API will check next port.
* `unreserve_port(reservation: PortReservation) -> None:` - stop reservation of port
* `find_free_port(connection: "AsyncConnection", port: int, count: int = 10) -> int:` - check and return free port

Port reservation is used in `Stream`, when passed `port` in constructor.

There is mechanism to clean-up after reservation in case of any python script exception.

Reservation creates UDP socket, which is keep alive during traffic. After that socket is closed.

### `StressTrafficManager` API
StressTrafficManager is a class for parallel execution of various traffic type organised into streams. User has full control of starting and stopping them. During the execution time all completed streams (run for a randomly selected duration)
are replaced by new instances until user decides to stop or pause them.

* `def start_all(
  sut_connection: "Connection",
  src_ips: list[Union[str, "IPv4Interface", "IPv6Interface"]],
  dst_ip: Union[str, "IPv4Interface", "IPv6Interface"],
  clients_connections: list["Connection"],
  traffic_classes: dict[TrafficTools, dict[str, Type["Traffic"]]],
  num_streams: int,
  start_port: int = 5001,
  min_dur: int = 10,
  max_dur: int = 21600,
  min_size: int = 64,
  max_size: int = 64000,
  protocols: list[Protocols] = [Protocols.ICMP, Protocols.UDP, Protocols.TCP, Protocols.SCTP],
  traffic_tools: list[TrafficTools] = [
  TrafficTools.PING,
  TrafficTools.IPERF2,
  TrafficTools.IPERF3,
  TrafficTools.NETPERF,
  ],
  comm_type: Optional[CommunicationType] = None) -> None`- Submit the specified number (num_streams) of streams and trigger monitoring thread to replace the completed
  streams with new instances until stop_all()/pause_all() is issued.
* `def stop_all(self) -> None` - Stop all running streams. In order to generate new traffics another instance of StressTrafficManager must be created.
* `def pause_all(self, duration: Optional[int]) -> None` - Stop all running streams. Traffic generation can be resumed after specified duration or (if not specified) by calling resume_all() method.
* `def resume_all(self) -> None` - Resume the parallel execution after pause.

> [!CAUTION]
> When using SSHConnection for StressTrafficManager, it's crucial to ensure a sufficient limit for SSH sessions. By default, 
> the SSH server on Linux accepts 10 parallel sessions. This might not be enough, even when executing 5 traffic streams 
> simultaneously, as there are numerous other commands executed in the background.
> To increase this limit on Linux, please adjust the MaxSessions parameter in /etc/ssh/sshd_config to a value at least 3x higher 
> than the number of streams you plan to run concurrently. Don't forget to restart the sshd service after modifying the configuration.


### Validation Criteria

`validate` API parameters are `validation_criteria` dictionaries. To make generic way of validation for traffics, we prepared mechanism to define own `validation functions`. `Validation function` implemented by user should return boolean value. That method will be called in `validate` API for each stream/traffic.
User can define various `validation functions` and use them depending on needs:
- for both server and client (`common_validation_criteria`),
- separately for server (`server_validation_criteria`)
- separately for clients (`clients_validation_criteria`).

Supported combinations:
* only common
* only server
* only clients
* server + clients

Expected structure of `validation_criteria` dictionary is:

`{<callable function>: {"keyword parameter for method": value_of_parameter, ...}, ...}`

Expected `callable function` definition:
* first argument is the result of finished traffic (e.g. list of `IntervalResult` objects from Iperf3) - that parameter will be provided inside `validate` API automatically.
* parameters for validation passed as keyword arguments

`callable function` will be executed inside `validate` of Traffic like:

`all(callable_function(results, **params) for callable_function, params in validation_criteria.items())`

It's recommended to group validation functions in one place like validation_criteria.py for better organization. For `validation_criteria` dictionary need to just import function.

Example implementation of `validate_criteria` and validation function:
```python
validation_criteria = {validate_traffic_bitrate: {"minimum": 4500}, validate_traffic_count: {"count": 10}}
def validate_traffic_bitrate(results: List["Iperf3IntervalResult"], *, minimum: int) -> bool:
    """
    Validate bitrate.

    :param results: List of Iperf3IntervalResult
    :param minimum: Minimum value of bitrate in interval result.
    :return: Status of validation.
    """
    for result in results:
        bandwidth = int(result.bitrate.split()[0])
        if bandwidth < minimum:
            logging.debug(f"{result} contains bitrate less than {minimum}")
            return False
    return True
(...)
def validate_traffic_count(results: List["Iperf3IntervalResult"], *, count: int) -> bool:
    is_count_correct = len(results) == count
    if not is_count_correct:
        logging.debug(f"{results} contain not expected amount of results, expected {count}")
    return is_count_correct
```

## OS supported:

* LNX
* WINDOWS
* FREEBSD
* ESXI

## Issue reporting

If you encounter any bugs or have suggestions for improvements, you're welcome to contribute directly or open an issue [here](https://github.com/intel/mfd-traffic-manager/issues).