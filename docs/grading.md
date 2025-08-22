# How to specify config for final grade

To configurate how final grade is computed you need to specify it in the course yaml config
(look at `.manytask.example.yml` for example).

## Grading process logic

Each grade is described by its value and conditions needed to achieve it.
Values are UNIQUE INTEGERS organized with respect to the logic <<THE HIGHER THE VALUE, THE BETTER THE GRADE>>,
it is CRUCIAL since during the evalutation process program tries to fit student into the specified patterns
from the highest grade to the lowest and stops this process with the first suitable mark.

Conditions are represented in the form of the list of dicts, those dicts consist of Key-Value pairs.

- `Key` is a STRING that specifies path in the student's grade.
- `Value` is an INTEGER or FLOAT that specifies minimum value of the attribute on the path `Key`.

The student's grade dict meets the conditions of the grade dict if ALL values by their paths (`Keys`)
are greater or equal than corresponding `Values` in the grade dict.
The student's grade dict meets the conditions of the list of grade dicts if it meets the conditions of AT LEAST ONE of the grade dicts inside it.
In the words of logic, each grade config is represented by `Disjunctive normal form` -- list of dicts.
Each dict inside this list represents a `Conjunction`.

## Grade config example

Consider your course has 2 large tasks and many basic tasks, so the final grade depends on the number of completed
large tasks and percent of completed basic tasks in a way that completing a large task decreases the share of basic tasks needed to obtain the same mark.

For 5 you need to complete either:

- 2 large tasks and 80% of basic tasks OR
- 1 large task and 90% of basic tasks

For 4 you need to complete either:

- 2 large tasks and 70% of basic tasks OR
- 1 large task and 80% of basic tasks

For 3 you need to complete either:

- 2 large tasks and 60% of basic tasks OR
- 1 large task and 50% of basic tasks

Otherwise, student fails and gets 2, then your config would look like this:

```yaml
grades:
    5: [
      {
        "percent": 90,
        "large_count": 1,
      },
      {
        "percent": 80,
        "large_count": 2,
      }
    ]
    4: [
      {
        "percent": 80,
        "large_count": 1,
      },
      {
        "percent": 70,
        "large_count": 2,
      }
    ]
    3: [
      {
        "percent": 60,
        "large_count": 1,
      },
      {
        "percent": 50,
        "large_count": 2,
      }
    ]
    2: [
      {
        "": 0
      }
    ]
```

You could easily apply pattern (of grade 2) from this example to make empty, mocked conditions for the lowest grade.

It is worth mentioning that suggested system is quite flexible and allows you to use both high level features, like
`percent`, `large_count` or `total_score` and make more specific condtions, like achieving a certain minimum
score in a chosen task. For example, if you want to grade students with 5 if they did not solve any big homeworks, but got 100 points for task `impossible` you could achieve it in the following fashion.

```yaml
grades:
    5: [
      {
        "percent": 90,
        "large_count": 1,
      },
      {
        "percent": 80,
        "scores/impossible": 100,
      }
    ]
    ...
```

Moreover, you could specify the minimum score needed to consider large task solved,
but it is a part of a task config rather than a feature of the grading system.
