# Pipelines

This is the most important part of the checker. Pipelines are used to actually check and grade the solution.   
Each pipeline is a sequence of plugins. Each plugin (pipeline stage) have arguments, run_if condition and return exclusion result. 

Please refer to the [plugins configuration](./3_plugins.md) for more details on pre-defined and custom plugins.


## 3 pipeline types

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
