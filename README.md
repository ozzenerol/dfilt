# dfilt

A small DNS filter written in [Iris](https://github.com/ozzenerol/iris). It listens on UDP, drops queries for blacklisted domains, and forwards the rest to upstream resolvers.

## Build

```sh
cd src
iris build main.iris -o dfilt
```

## Run

```sh
./dfilt --configPath config.json
```

`config.json`:

```json
{
    "port": 8000,
    "timeoutSeconds": 2,
    "upstreams": ["1.1.1.1", "8.8.8.8"],
    "blacklistPath": "../data/blacklist.txt"
}
```

The blacklist is one domain per line.

## Test

```sh
dig @127.0.0.1 -p 8000 example.com
./loadtest.py --clients 100 --requests 5000
```
