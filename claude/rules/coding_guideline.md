# Coding Guidelines

This document provides comprehensive coding guidelines for programming and software development.

## Clean Code

### File Design

- 80-120 characters per line
- 200-500 lines per file
- Order from high abstraction to low abstraction
  - Write called functions immediately after calling functions
- Place closely related concepts near each other, unrelated concepts in different files
  - Define classes with their specific enums and exception classes in the same file
- Separate object creation and execution (make dependencies unidirectional, separate creation and execution responsibilities)
  - Object creation and configuration only in main, AbstractFactory, or DI containers

### Class Design

#### Class Policy

- Class has single responsibility (SRP)
- Minimize number of fields and methods
  - All methods use all fields evenly (high cohesion)
  - Split class when field-method correspondence separates
- Fields and methods are private by default, public only when necessary for exposure

#### Class Principles

- Class name represents responsibility
- Method order: public → private
- Prohibit fields and methods not used in specific domains
  - Wrap objects that are not user-defined types
  - Define interfaces for user-defined type objects
- Separate internal implementation through interfaces (loose coupling)
- One exception class per concept
- Don't practice feature envy (Law of Demeter)
- Use DTOs for component interactions

### Function Design

#### Function Policy

- Function does exactly one thing
  - Split functions that do multiple things
    - Extract duplications
    - Extract by paragraphs (SRP)
    - Extract control structures
    - Separate different responsibilities in iterations by splitting iterations themselves
    - Extract commands and queries separately (Command Query Responsibility Segregation)
- Express function processing with multiple more specific functions
  - One abstraction level per function
  - Make readable as sequence of to-clauses from high to low abstraction

#### Function Principles

- 0-3 arguments
  - Create parameter class when many arguments
  - Express processing order through arguments
  - Provide information through keyword arguments
- 2-4 lines with maximum one indentation level
- Define variables just before use (shorten variable lifetime)
- Convert temporary variables to functions when used in processing
- Make control structures 2 lines by functionalizing conditions and processing
- Distinguish between normal-to-normal branching and normal-to-exception branching
- Return early for exception handling in conditional branches (guard clauses)
- Use polymorphism for complex if/match statements (Pluggable Object)

### Naming Conventions

#### Naming Policy

- One concept, one word (similar usage gets similar names, different usage gets different names)
- Command functions clarify side effects, query functions clarify returned objects in naming
- Name length corresponds to scope size (short scopes allow abbreviated names)
- Name meaningful constants and long expressions (temporary variables)

#### Naming Principles

- Use programming terms and domain terms
- Precise word selection (get/fetch/download)
- Add attributes
  - Units (length→chars/start_ms)
  - Prefixes/suffixes (unsafe_/untrust_/plaintext_/_urlenc)
  - Boolean (is/has/can/show/should/enabled)
- Omit unnecessary words

### Comments

#### Comment Policy

- Minimize comments (excellent code > comments)
- No docstrings unless public API
- Explain intentions that cannot be expressed in code
- Code defects (TODO)

#### Comment Content

- High-level description of behavior
- Precise description of processing
- Information-dense terminology
- Avoid ambiguous pronouns
- Excellent examples of input/output

## Kent Beck's Test Driven Development (TDD)

### Rules

- Write new code only when tests fail, don't write new tests during this time
- Remove duplication

### Process

1. Write TODO list
2. Write one test (write minimal empty implementation if test cannot run)
3. Run all tests and confirm one failure (Red)
4. Make minimal change for test to pass
5. Run all tests and confirm success (Green)
6. Remove duplication (Refactoring)

### Test Design Principles

#### Test Policy

- Write tests only for your own code
- One concept per test function
- Prioritize readability (allow long names and mental mapping)
- Make tests independent
- Delete and back out tests that don't work well
- Leave failing tests when ending personal work
- Test volume depends on estimated product lifetime

#### Test Rules

- Write tests for complex public methods
- Focus testing on operations, control structures, and polymorphism
- Test function name should be reason test was written
- Test methods up to 3 lines
- Write assertions first (Assertion First)
- Write processing to test (Act)
- Create necessary objects (Arrange)

## Martin Fowler's Refactoring

### Process

1. Write tests
2. Split work into small refactoring tasks
3. Commit after each successful refactoring

### Refactoring Timing

- Inaccurate names
- Duplicated code
- Functions with many parameters
- Global objects
- Control structures of same format
- Variables, functions, classes, modules with multiple responsibilities, scattered responsibilities, or no responsibilities
- Classes and modules that are not high cohesion, low coupling
- Inheritance where supertype methods are not needed
- Primitive type obsession
- Object groups that are not of same class
- Mutable objects
- Data classes with no methods other than getters/setters
- Functions that operate on objects returned by methods of function-like objects
- Comments that hide code smells

### Refactoring Principles

- Distinguish between feature addition and refactoring
- Be aware of refactoring trade-offs
- When concerned about performance, first make it easy to tune, then make it faster gradually
- Encapsulation that doesn't change external behavior is important

## Design Principles

### SOLID Principles

#### Single Responsibility Principle (SRP)

- Module has single role
- Split modules with different roles

#### Open-Closed Principle (OCP)

- Module is extensible without modification
- Separate components into level hierarchies to avoid impact of changes

#### Liskov Substitution Principle (LSP)

- Supertype can be replaced with subtype
- Subtype must have all properties of supertype

#### Interface Segregation Principle (ISP)

- Separate methods that supertype has but subtype doesn't use from subtype
- Remove dependencies between methods through role-specific interfaces

#### Dependency Inversion Principle (DIP)

- Subtype depends on interfaces, not supertype concrete types
- Don't reference concrete types that change easily

### DRY Principle (Don't Repeat Yourself)

- Abstract and eliminate duplicate parts

### YAGNI Principle (You aren't going to need it)

- Implement only currently needed features

### Minimum Visibility Principle

- Default to the most restricted visibility the language permits
  - Functions not used outside the file: file-private or module-private
  - Modules/packages: expose only to the files/modules that actually depend on them
    - Python: `_` prefix for module-internal names (convention; skipped by `from M import *`)
    - Rust: prefer `pub(crate)` or `pub(super)` over `pub`
- Promote visibility only when an external caller is added
- Treat a wide public API as a coupling surface: the smaller, the safer to refactor

### F.I.R.S.T (Clean Test Conditions)

- Fast
- Independent
- Repeatable
- Self-Validating
- Timely

### Kent Beck's Four Rules for Simple Design

- Run all tests
- No duplication
- Express programmer intent
- Minimize number of classes and methods

### Law of Demeter

- Function should only use methods of objects visible to the function
- Should not know about internals of objects returned by that object's methods

### Eric Evans's Domain Driven Design (DDD)

#### DDD Implementation Patterns (Lightweight DDD)

##### Domain Model

- Model that organizes small target domain as independent object model
- Create domain model from concerns, not features
  - Don't create as part of feature (feature-centric design creates dependencies)
  - Concern of wanting to know age → Create age class as place to put calculation logic

##### Domain Object

- Object that combines data and processes of small target domain
- Design objects with only necessary constraints and related methods using non-primitive types

##### Value Object

- Object with constraints and related methods for values (create per data type)
- Fields are immutable (define fields in constructor, don't create setters)
- Impose constraints on primitive types (int: -2.1B to 2.1B range, str: infinite length with free format, ...)
- Consider Value Objects of same type with all equal fields as identical

##### Entity

- Mutable Value Object that considers same-type Value Objects with equal identifiers as identical

##### Collection Object

- Object with constraints and related methods for collections
- Don't create getters for collection itself, encapsulate internal collection
- When creating getters, create only methods that extract necessary elements
- When creating setters, return result as new Collection Object of same type

##### Classification Object

- Object with class/object per classification using enum types
- Has class/object per classification as fields and interface methods
- Express state transition constraints as "source": set("destination", ...) to determine transition possibility
- Use classification object when handling classes/objects identifiable through interface
- Use DI (dependency injection) when injecting usage-restricted objects through interface into class

## Other Important Concepts

### Object-Oriented Programming (OOP)

- Encapsulation: Encapsulate data and processes, restrict direct external access
- Polymorphism: Have different class objects possess same methods
- Inheritance: Generally discouraged, use only in appropriate use cases

### Functional Programming (FP)

- Variable immutability: Variable values cannot be changed
- Referential transparency: Eliminate side effects
- Function objectification: Treat functions as objects
- Lazy evaluation: Execute necessary value processing just before operation execution

### Architecture

- Separate policy from details
- Delay decisions about DB, web servers, etc., make them abstract to reduce dependencies
- Good architects minimize number of decisions not made

## Summary

These guidelines aim to improve code quality with emphasis on maintainability, extensibility, and testability. Rather than strictly applying all principles, it's important to apply them appropriately based on project nature and team circumstances.
