# Chapter 3: Certificate Loader

Welcome to Chapter 3!

In the previous chapter, [TLS Credentials Factory](02_tls_credentials_factory.md), we built a "Factory" that creates secure, locked briefcases (TLS Credentials) for our messages.

However, we left one big question unanswered: **Where do the keys come from?**

In Chapter 2, we magically assumed we had the `private_key` and `cert_chain` ready to go. In reality, these are files sitting somewhere on your hard drive.

## The Motivation: The Keymaster

Imagine you run a hotel. You (the software) don't want to carry every single key in your pocket. You also don't want to hardcode the room numbers into your brain, because room numbers change.

You need a **Keymaster**.
1.  You tell the Keymaster: "I need the keys for the Manager's Office."
2.  The Keymaster looks up the location in a registry (Environment Variables).
3.  The Keymaster walks to the cabinet, grabs the physical key (File I/O), and hands it to you.

**The Problem:** Reading files in C++ can be messy. You have to handle opening streams, checking if the file exists, reading bytes, and closing the file. If you do this in every single service, your code becomes messy and hard to read.

**The Solution:** The **Certificate Loader**. It is a utility that abstracts away the file system. It simply says: "Give me the path, and I will give you the data."

## Concept 1: The Configuration (The Map)

First, we need a way to tell our program *where* the files are located without rewriting the code. We use a structure called `CertConfig`.

Think of this as a treasure map. It doesn't hold the treasure (the keys); it just holds the coordinates (the file paths).

```cpp
struct CertConfig {
    std::string cert_chain_path;  // Path to your Public ID
    std::string private_key_path; // Path to your Secret Key
    std::string ca_cert_path;     // Path to the Trust Anchor
};
```

**Why is this better?**
We can change these paths (e.g., from `/tmp/certs` to `/etc/pqc/keys`) instantly without recompiling our C++ code.

## Concept 2: The Loader (The Action)

Next, we need the function that actually does the work. This function takes a filepath and returns the raw content of that file as a string.

It functions as a "dumb pipe." It doesn't care if the file contains a classical RSA key or a futuristic Post-Quantum ML-DSA key. It just loads bytes.

```cpp
// The Promise (Header file)
std::string LoadFileContents(const std::string& path);
```

## Solving the Use Case

Let's see how a developer uses this in the real application.

We rely on **Environment Variables** to configure our paths. This is a standard practice in cloud applications (like Docker or Kubernetes).

### Step 1: Setting the Environment
Before running the app, the user (or a script) sets these variables:

```bash
export PQC_CERT_PATH="certs/server.pem"
export PQC_KEY_PATH="certs/server.key"
export PQC_CA_PATH="certs/ca.pem"
```

### Step 2: Using the Loader in C++
Here is how we use the loader to get our configuration.

```cpp
// 1. Automatically grab paths from the environment
CertConfig config = CertConfig::FromEnv();

// 2. Pass this config to the Factory we built in Chapter 2
auto creds = CreateServerCredentials(config);
```

**What just happened?**
1.  `FromEnv()` looked at the environment variables.
2.  It filled the `CertConfig` struct with `"certs/server.pem"`, etc.
3.  The Factory then used `LoadFileContents` to read the actual data.

## Under the Hood: Implementation

Let's look at how the sausage is made. This logic is contained in `common/src/cert_loader.cpp`.

```mermaid
sequenceDiagram
    participant App as Application
    participant Config as CertConfig
    participant OS as Operating System
    participant Loader as File Loader
    participant Disk as Hard Drive

    App->>Config: FromEnv()
    Config->>OS: Get "PQC_CERT_PATH"
    OS-->>Config: Returns "/path/to/server.pem"
    Config-->>App: Returns Config Object

    App->>Loader: LoadFileContents("/path/to/server.pem")
    Loader->>Disk: Open File Stream
    Disk-->>Loader: Stream of Bytes
    Loader-->>App: Returns std::string (PEM Data)
```

### The File Loading Logic
Reading a file into a string in C++ looks like this:

```cpp
std::string LoadFileContents(const std::string& path) {
    // 1. Open the file in binary mode
    std::ifstream file(path, std::ios::in | std::ios::binary);
    
    // 2. Check if it exists
    if (!file) {
        throw std::runtime_error("Failed to open: " + path);
    }

    // 3. Read the whole buffer into a string stream
    std::ostringstream ss;
    ss << file.rdbuf();
    
    // 4. Return the string
    return ss.str();
}
```

**Explanation:**
*   `std::ifstream`: Input File Stream. It connects our code to the file on disk.
*   `throw`: If the file isn't found (maybe you made a typo in the path), we stop the program immediately with an error. Safety first!
*   `ss << file.rdbuf()`: This is a C++ trick to efficiently copy all file contents into memory at once.

### The Environment Logic
How do we read the environment variables?

```cpp
CertConfig CertConfig::FromEnv() {
    // 1. Read variables from the OS
    const char* cert = std::getenv("PQC_CERT_PATH");
    const char* key = std::getenv("PQC_KEY_PATH");
    const char* ca = std::getenv("PQC_CA_PATH");

    // 2. Validate they exist
    if (!cert || !key || !ca) {
        throw std::runtime_error("Missing PQC environment variables!");
    }

    // 3. Return the struct
    return CertConfig{cert, key, ca};
}
```

## PQC Context: RSA vs. ML-DSA

You might be wondering: "This chapter is part of a Post-Quantum Cryptography project. Where is the quantum math?"

That is the beauty of this abstraction! The **Certificate Loader** is agnostic.

*   If you run the script `scripts/generate_rsa_certs.sh`, you get standard RSA keys. The loader reads them as text.
*   If you run `scripts/generate_mldsa_certs.sh`, you get **ML-DSA-65** (Post-Quantum) keys. The loader *also* reads them as text.

Because both file types are encoded in **PEM format** (those blocks starting with `-----BEGIN PRIVATE KEY-----`), our loader doesn't need to change. We switch from classical security to post-quantum security just by changing the files on the disk!

## Conclusion

In this chapter, we built the **Certificate Loader**.

1.  We created `CertConfig` to hold our file paths.
2.  We implemented `LoadFileContents` to handle the dirty work of file I/O.
3.  We connected this to Environment Variables for easy configuration.

Now we have the **Contracts** (Chapter 1), the **TLS Factory** (Chapter 2), and the **Loader** (Chapter 3). We technically have everything we need to run a server.

But... does it actually work? Can we prove that our cryptographic keys are valid?

In the next chapter, we will build a test suite to verify our setup.

[Next Chapter: PQC Validation Suite](04_pqc_validation_suite.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)