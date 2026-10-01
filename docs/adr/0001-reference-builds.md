# Immutable references and per-version dynamic modules

Status: accepted for the initial build milestone.

## Context

Two exact Exim release trees were supplied as read-only references. Their misc
module descriptor matches, but debug/log APIs and other internal types differ.

## Decision

Hash every reference file. Copy sources into disposable build directories, apply
versioned patches there, compile full Exim and a separately built dynamic Observer
module using that Exim's generated headers. Use observer_miscmod.so and the native
observer_module_info export. Retain no universal-binary claim. Check source hashes
before and after tests. Build/test artifacts use private spool directories.

## Consequences

No edits, Local/Makefile files or compiler products enter the supplied trees.
Compiler/version combinations have isolated build outputs. Patches preserve native
Exim formatting and contain only the changes needed for each milestone.
