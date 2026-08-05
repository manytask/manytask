# Checker Pipelines and Plugins

This page describes how pipelines work in the checker and how to use and write plugins for them.

You can refer to the [course-template](https://github.com/manytask/course-template) repository for examples of plugins usage and custom plugins development.


## Pipelines

This is the most important part of the checker. Pipelines are used to actually check and grade the solution.   
Each pipeline is a sequence of plugins. Each plugin (pipeline stage) have arguments, run_if condition and return exclusion result. 


### 3 pipeline types

There are 3 types of pipelines you need to define in `.checker.yml` file:
* `global_pipeline` - pipeline to be executed once for all checker repository.  
    You can place here any general compilation, installation, etc.  
* `tasks_pipeline` - pipeline to be executed for each task.  
    You can place here any task-specific compilation, installation, etc.  
    For example, you run `pytest` by default, but for some tasks you want to have MR checked first.  
    (can be re-defined in `.task.yml` file)
* `report_pipeline` - pipeline to be executed for each task after all tests are passed (not failed).  
    You can place here any task-specific score reporting, etc.  
    For example, you can report the score to the Manytask platform, but for some tasks you want to have MR checked first.  
    (can be re-defined in `.task.yml` file)


## Plugins

Plugin is a single stage of the pipeline, have arguments, return exclusion result. 

```yaml
  tasks_pipeline:
    - name: "Check forbidden regexps"
      fail: fast  # fast, after_all, never
      run: "check_regexps"
      args:
        origin: "${{ global.temp_dir }}/${{ task.task_sub_path }}"
        patterns: ["**/*.py"]
        regexps: ["exit(0)"]

    - name: "Run linter"
      run_if: ${{ parameters.run_linting }}
      fail: after_all  # fast, after_all, never
      run: "run_script"
      args:
        origin: ${{ global.temp_dir }}
        script: "python -m ruff --config=pyproject.toml ${{ task.task_sub_path }}"
```

In a nutshell, it is a Python class overriding abstract class `checker.plugins.PluginABC`:

> ::: checker.plugins.base.PluginABC

Note that each plugin should override `checker.plugins.PluginABC.Args` class to provide arguments validation. Otherwise, empty arguments will be passed to `run` method.

> ::: checker.plugins.base.PluginABC.Args


Each plugin output `checker.plugins.PluginOutput` class when executed successfully. 

> ::: checker.plugins.base.PluginOutput

In case of error, `checker.exceptions.PluginExecutionFailed` have to be raised.
> ::: checker.exceptions.PluginExecutionFailed

!!! note  
    Base Plugin class will handle all ValidationErrors of Args and raise error by itself.  
    So try to move all arguments validation to `Args` class in `pydantic` way.


### How to use plugins

Plugins are used in the pipelines described in `.checker.yml` file. When running a pipeline the checker will validate plugin arguments and run it.

The following plugins are available out of the box, here is the list with their arguments:


* `run_script` - execute any script with given arguments  

    > ::: checker.plugins.scripts.RunScriptPlugin.Args

* `safe_run_script` - execute script withing firejail sandbox 

    > ::: checker.plugins.firejail.SafeRunScriptPlugin.Args

* `check_regexps` - error if given regexps are found in the files  

    > ::: checker.plugins.regex.CheckRegexpsPlugin.Args

* `aggregate` - aggregate results of other plugins (e.g. sum/mean/mul scores)  

    > ::: checker.plugins.aggregate.AggregatePlugin.Args

* `report_score_manytask` - report score to manytask  

    > ::: checker.plugins.manytask.ManytaskPlugin.Args

* `check_gitlab_merge_request` - [WIP] check gitlab MR is valid (no conflicts, no extra files, has label etc.)

    > ::: checker.plugins.gitlab.CheckGitlabMergeRequestPlugin.Args

* `collect_score_gitlab_merge_request` - [WIP] search for score by tutor in gitlab MR comment    

    > ::: checker.plugins.gitlab.CollectScoreGitlabMergeRequestPlugin.Args


### How to write a custom plugin

To write a custom plugin you need to create a class inheriting from `checker.plugins.PluginABC` and override `_run` method, `Args` inner class and set `name` class attribute.

```python
from random import randint
from checker.plugins import PluginABC, PluginOutput
from checker.exceptions import PluginExecutionFailed
from pydantic import AnyUrl

class PrintUrlPlugin(PluginABC):
    """Plugin to print url"""

    name = "print_url"

    class Args(PluginABC.Args):
        url: AnyUrl

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        if randint(0, 1):
            if verbose:
                raise PluginExecutionFailed("Verbose error, we got randint=1")
            else:
                raise PluginExecutionFailed("Random error")
        
        return PluginOutput(
            output=f"Url is {args.url}",
            percentage=1.0,  # optional, default 1.0 on success
        )
```

!!! important  
    The Plugin must implement `verbose` functionality!  
    If `verbose` is `True` the plugin should provide all info and possible debug info.  
    If `verbose` is `False` the plugin should provide only public-friendly info, e.g. excluding private test output.

!!! note
    It is a nice practice to write a small tests for your custom plugins to be sure that it works as expected.
