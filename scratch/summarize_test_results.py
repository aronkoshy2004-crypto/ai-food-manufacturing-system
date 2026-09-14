import json

data = json.load(open('scratch/live_inspection_test_results.json', encoding='utf-8'))
for i, tc in enumerate(data):
    print(f"=== TEST CASE {i+1}: {tc['commodity']} - {tc['type']} ===")
    print(f"  Annotated Image: {tc['annotated_image_url']}")
    print(f"  Inference Time:  {tc['inference_time_ms']} ms")
    print(f"  Defects Count:   {tc['total_defects_count']}")
    print(f"  Healthy Count:   {tc['healthy_specimens_count']}")
    
    # Group defects by class
    d_classes = {}
    for d in tc['defects']:
        cls = d['defect_class']
        d_classes.setdefault(cls, []).append(d['confidence'])
    for cls, confs in d_classes.items():
        print(f"    * Defect Class '{cls}': {len(confs)} detected, Max Conf: {max(confs)*100:.1f}%, Min Conf: {min(confs)*100:.1f}%, Avg: {sum(confs)/len(confs)*100:.1f}%")
        
    # Group healthy by class
    h_classes = {}
    for h in tc['healthy']:
        cls = h['specimen_class']
        h_classes.setdefault(cls, []).append(h['confidence'])
    for cls, confs in h_classes.items():
        print(f"    * Healthy Class '{cls}': {len(confs)} detected, Max Conf: {max(confs)*100:.1f}%, Min Conf: {min(confs)*100:.1f}%, Avg: {sum(confs)/len(confs)*100:.1f}%")
    print()
