# Pipelines

This is the most important part of the checker. Pipelines are used to actually check and grade the solution.   
Each pipeline is a sequence of plugins. Each plugin (pipeline stage) have arguments, run_if condition and return exclusion result. 

Please refer to the [plugins configuration](./3_plugins.md) for more details on pre-defined and custom plugins.


## 3 pipeline types

There are 3 types of pipelines you need to define in `.checker.yml` file:
* `global_pipeline` - pipeline to be executed once for all checker repository.  
    You can place here any general compilation, installation, etc.  
* `task_pipeline` - pipeline to be executed for each task.  
    You can place here any task-specific compilation, installation, etc.  
    For example, you run `pytest` by default, but for some tasks you want to have MR checked first.  
    (can be re-defined in `.task.yml` file)
* `report_pipeline` - pipeline to be executed for each task after all tests are passed (not failed).  
    You can place here any task-specific score reporting, etc.  
    For example, you can report the score to the Manytask platform, but for some tasks you want to have MR checked first.  
    (can be re-defined in `.task.yml` file)

```yaml
# .checker.yml
...
testing:
  # once
  global_pipeline:
    - name: "Install requirements"
      run: "run_script"
      args:
        ...
  # for each task
  task_pipeline:
    - name: "Run pytest"
      run: "pytest"
      args:
        ...
  # for each task after task_pipeline is passed
  report_pipeline:
    - name: "Report Score Manytask"
      run: "report_score_manytask"
      args: 
        ...
...
```

## Single pipeline stage

Each pipeline stage is a plugin called with arguments. Here is the example of a single pipeline stage:
```yaml
  - name: "Check forbidden regexps"  
    fail: fast
    run: "check_regexps"
    run_if: true
    register_output: "forbidden_regexps"
    args:
      origin: "/tmp/origin"
      patterns: ["**/*.py"]
      regexps: ["exit(0)"]
```

* `name`: Human-readable name of the pipeline stage to be shown in the logs.  
* `fail`: Defines how to handle the failure of this pipeline stage.  
    * `fast` - (default) fail fast, stop the pipeline and fail the task immediately.  
    * `after_all` - fail after all pipeline stages are executed.  
    * `never` - ignore the failure of this pipeline stage.
* `run`: key name of the plugin to be executed. Will be searched within pre-defined and custom plugins.
* `run_if`: condition to run this pipeline stage. Cast to bool, `true` by default.
* `register_output`: name of the output to be registered in `outputs` variable. The `PipelineStageResult` object will be stored in `outputs` dict with this name.
* `args`: arguments to be passed to the plugin.  
    Arguments are validated by `pydantic` library as defined by each individual plugin.  


### Templating in Tester Pipelines

You can use [jinja2](https://jinja.palletsprojects.com/en/3.0.x/) templating in `.checker.yml` file pipeline arguments and `run_if` conditions.  
They can be used with `${{ ... }}` syntax, expression within this brackets will be evaluated before plugin execution. For example:
```yaml
  report_pipeline:
    - name: "Report Score Manytask"
      run: "report_score_manytask"
      args:
        origin: "${{ global.temp_dir }}/${{ task.task_sub_path }}"
        patterns: ["**/*.py"]
        username: ${{ global.username }}
        task_name: ${{ task.task_name }}
        score: ${{ outputs.test_output.percentage }}
```


The available variables are:

* `global` - global parameters  
    
    > ::: checker.tester.GlobalPipelineVariables

* `task` - task parameters  
    
    > ::: checker.tester.TaskPipelineVariables

* `parameters` - default parameters
    
    > ::: checker.configs.checker.CheckerParametersConfig

* `env` - environment variables dict in the moment of running checker

* `outputs` - outputs of previous pipeline step if `register_output` is set, dict of string to `checker.plugins.PluginOutput` objects  
    
    > ::: checker.pipeline.PipelineStageResult


### Pipeline stage result

Each stage can optionally register its output in `outputs` context to be used by the next stages.  
e.g. register percentage of passed tests to be used in the next stage to report the score.

Each pipeline processes internally as `PipelineStageResult` object. It contains the following fields:

> ::: checker.pipeline.PipelineStageResult

And can be accessed in the next pipeline stages using templating syntax `${{ outputs.<registered-name>.<result-field> }}`
