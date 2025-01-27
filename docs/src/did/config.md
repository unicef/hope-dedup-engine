### Default Configuration

The default configuration can be managed directly through the **admin panel**, providing a simple way to modify settings without changing the codebase. Navigate to:

    Home › Constance › Config  

This section contains the **default configuration**, which applies to the system globally. It defines the base settings for the application and ensures consistent behavior across all deduplication sets.  

#### Key Parameters:  

##### **MODEL_NAME**
Specifies the face recognition model to be used for **encoding** face landmarks. **VGG-Face** (default)

##### **DETECTOR_BACKEND**  
Specifies the face detector backend used during the **Face Detection** and **Alignment** stages to locate faces and ensure consistent facial alignment in images. **RetinaFace** (default)

##### **FACE_DISTANCE_THRESHOLD**  
  Specifies the maximum allowable **distance** between two face embeddings for them to be considered a match. This **similarity threshold** is crucial for assessing whether two faces belong to the same individual. Lower values result in stricter matching, while higher values allow for more lenient matches.  

---

### Custom Configuration

Custom configurations can be created for specific **deduplication sets** through the **admin panel** by navigating to:  

    Home › API › Configs  

At this path, you can define a custom configuration in **JSON format**. Custom configurations include only the parameters you wish to override from the default configuration.  

#### Details
- Parameters not included in the custom configuration will default to the values from the global configuration and will be used by the system in subsequent calculations. This ensures that all required parameters are available, even if they are not explicitly defined in the custom configuration.  
- A custom configuration can be associated with a specific deduplication set via:  

        Home › API › Deduplication sets › <specific_deduplication_set>

- If no custom configuration is associated with a deduplication set, the system will entirely use the **default configuration** for that set.  

- Parameter names in custom configurations are case-sensitive and must be in **lowercase**.

#### Example Custom Configuration:  
To override only the **FACE_DISTANCE_THRESHOLD** parameter, your custom configuration can look like this:  

```json
{
  "face_distance_threshold": 0.7
}
```

The configuration will undergo **validation** during saving to confirm the JSON structure and ensure all keys are valid and match the default configuration. Any invalid entries will prevent saving until corrected. 

This flexibility allows you to define tailored configurations for specific deduplication sets, ensuring precise control over application behavior while preserving the stability of default settings.
