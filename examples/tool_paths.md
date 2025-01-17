Below are some known good pickup/dropoff paths for various tool changers.

Feel free to create pull requests to add more.

### TapChanger
```
  params_dropoff_path: [{'z':0, 'y':4}, {'z':0, 'y':0}, {'z':-7.3, 'y':0}, {'z':-11.2, 'y':3.5}, {'z':-13.2, 'y':8}]
  params_pickup_path: [{'z':-13.2, 'y':8}, {'z':-11.2, 'y':3.5}, {'z':-7.3, 'y':0}, {'z':3, 'y':0, 'f':0.5, 'verify':1},  {'z':0, 'y':0}, {'z':0, 'y':4}]
```

### StealthChanger
```
  params_dropoff_path: [{'z':0, 'y':4}, {'z':0, 'y':0}, {'z':-12, 'y':0}]
  params_pickup_path: [{'z':-12, 'y':2}, {'z':-12, 'y':0}, {'z':1.5, 'y':0, 'f':0.5, 'verify':1}, {'z':0, 'y':0}, ]
```

### ClickChanger

```
  params_dropoff_path: [{'z':0, 'y':10}, {'z':0, 'y':0}, {'z':-10.5, 'y':0}, {'z':-10.5, 'y':10}]
  params_pickup_path: [{'z':-10.5, 'y':10}, {'z':-10.5, 'y':0}, {'z':-4, 'y':0}, {'z':2.5, 'f':0.5, 'verify':1}, {'z':0}, {'y':10, 'z':0}]
```
