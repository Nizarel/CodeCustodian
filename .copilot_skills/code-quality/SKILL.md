---
name: code-quality
description: >
  Refactoring catalog and design pattern expertise for reducing complexity,
  improving maintainability, and applying SOLID principles.
---

# Code Quality Skill

## Refactoring Catalog

### Extract Method
When a function exceeds 50 lines or has high cyclomatic complexity:
```python
# BEFORE — monolithic function
def process_order(order):
    # validate (15 lines)
    # calculate totals (20 lines)
    # apply discounts (15 lines)
    # send notification (10 lines)

# AFTER — extracted methods
def process_order(order):
    validate_order(order)
    totals = calculate_totals(order)
    final = apply_discounts(totals, order.customer)
    send_order_notification(order, final)
```

### Replace Conditional with Polymorphism
When complex if/elif/else chains switch on type:
```python
# BEFORE
def calculate_area(shape):
    if shape.type == "circle":
        return math.pi * shape.radius ** 2
    elif shape.type == "rectangle":
        return shape.width * shape.height

# AFTER — polymorphism
class Circle:
    def area(self) -> float:
        return math.pi * self.radius ** 2

class Rectangle:
    def area(self) -> float:
        return self.width * self.height
```

### Introduce Parameter Object
When functions have >5 parameters:
```python
# BEFORE
def create_report(title, author, date, format, template, lang): ...

# AFTER
@dataclass
class ReportConfig:
    title: str
    author: str
    date: datetime
    format: str = "pdf"
    template: str = "default"
    lang: str = "en"

def create_report(config: ReportConfig): ...
```

### Replace Magic Numbers/Strings
```python
# BEFORE
if retry_count > 3:
    if status == "ERR_TIMEOUT":

# AFTER
MAX_RETRIES = 3
ERROR_TIMEOUT = "ERR_TIMEOUT"
if retry_count > MAX_RETRIES:
    if status == ERROR_TIMEOUT:
```

## SOLID Principles Applied

- **S — Single Responsibility**: Each function/class does one thing. Split when you see "and" in the description.
- **O — Open/Closed**: Use protocols/ABCs for extension points instead of modifying existing code.
- **L — Liskov Substitution**: Subclass must work wherever parent is expected.
- **I — Interface Segregation**: Small, focused protocols over large abstract bases.
- **D — Dependency Inversion**: Depend on abstractions (Protocol), inject concrete implementations.

## Complexity Reduction Guidelines

| Metric | Threshold | Action |
|--------|-----------|--------|
| Cyclomatic complexity | > 10 | Extract methods, use early returns |
| Cognitive complexity | > 15 | Simplify nesting, extract helpers |
| Function length | > 50 lines | Extract method |
| Parameter count | > 5 | Introduce parameter object |
| Nesting depth | > 4 | Use guard clauses, early returns |
| Class methods | > 20 | Split class by responsibility |

## Early Return Pattern
```python
# BEFORE — deeply nested
def process(data):
    if data is not None:
        if data.is_valid():
            if data.has_permission():
                return do_work(data)
    return None

# AFTER — guard clauses
def process(data):
    if data is None:
        return None
    if not data.is_valid():
        return None
    if not data.has_permission():
        return None
    return do_work(data)
```
