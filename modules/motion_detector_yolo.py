import cv2
import numpy as np
from collections import deque
from ultralytics import YOLO
import time
 
class TrackedVehicle:
    """
    Tracks one vehicle across frames.
    Uses STRICT consecutive-frame-difference logic
    to avoid false positives from YOLO bounding box jitter.
    """
    REAL_CAR_WIDTH_CM = 180
    FOCAL_LENGTH_PX   = 700
 
    # ── Thresholds (tuned to avoid jitter false positives) ──
    POTHOLE_STEP_PX   = 15    # single frame Y jump = pothole
    HUMP_STEP_PX      = 6     # per-frame movement = hump
    HUMP_MIN_FRAMES   = 6     # sustained frames needed
    BRAKE_GROW_PX     = 4     # box width growth per frame
 
    def __init__(self, vid, box, cls, conf):
        self.id          = vid
        self.cls         = cls
        self.conf        = conf
        self.box         = box
        self.last_seen   = time.time()
 
        self.y_buf       = deque(maxlen=20)
        self.x_buf       = deque(maxlen=20)
        self.w_buf       = deque(maxlen=20)
        self.t_buf       = deque(maxlen=20)
 
        # Smoothed Y (reduces YOLO jitter)
        self.y_smooth    = deque(maxlen=20)
        self.smooth_alpha= 0.4   # EMA smoothing factor
 
        # Event hold
        self.held_event  = 'normal'
        self.held_conf   = 0.0
        self.held_desc   = 'Road normal'
        self.held_until  = 0.0
        self.HOLD_SEC    = 1.8

        # Oncoming flag (True if vehicle appears to be approaching)
        self.oncoming = False
 
        self._update_buffers(box, conf)
 
    def _update_buffers(self, box, conf):
        x1,y1,x2,y2 = box
        cx = (x1+x2)//2
        cy = (y1+y2)//2
        bw = x2-x1
        self.y_buf.append(float(cy))
        self.x_buf.append(float(cx))
        self.w_buf.append(float(bw))
        self.t_buf.append(time.time())
 
        # Exponential moving average smoothing
        if self.y_smooth:
            prev = self.y_smooth[-1]
            self.y_smooth.append(
                self.smooth_alpha * cy + (1-self.smooth_alpha) * prev
            )
        else:
            self.y_smooth.append(float(cy))

        # Update oncoming estimate after buffers updated
        self._estimate_oncoming()
 
    def update(self, box, conf):
        self.box      = box
        self.conf     = conf
        self.last_seen= time.time()
        self._update_buffers(box, conf)

    def _estimate_oncoming(self):
        """Heuristic: if bounding-box width has been consistently
        growing over recent frames, the object is approaching (likely
        oncoming). Mark it so the detector can ignore it for rear-vehicle
        decisions.
        """
        if len(self.w_buf) < 6:
            self.oncoming = False
            return
        w = list(self.w_buf)
        deltas = [w[i] - w[i-1] for i in range(1, len(w))]
        mean_delta = sum(deltas) / len(deltas)
        mean_w = sum(w) / len(w) if w else 0.0
        rel_growth = (mean_delta / max(mean_w, 1.0))
        # Conservative thresholds: approaching if mean_delta > 3 px
        # and relative growth > 1%
        self.oncoming = (mean_delta > 3.0 and rel_growth > 0.01)
 
    def get_distance_m(self):
        x1,y1,x2,y2 = self.box
        bw = x2-x1
        if bw <= 0: return None
        return round((self.REAL_CAR_WIDTH_CM * self.FOCAL_LENGTH_PX)/(bw*100.0),1)
 
    def get_speed_kmh(self, dist_m):
        if len(self.x_buf)<4 or dist_m is None: return None
        try:
            xs = list(self.x_buf)
            ts = list(self.t_buf)
            dx = abs(xs[-1]-xs[0])
            dt = ts[-1]-ts[0]
            if dt<=0: return None
            ppm   = self.FOCAL_LENGTH_PX / max(dist_m,0.5)
            spd   = (dx/ppm)/dt * 3.6
            return round(spd,1) if 0<spd<120 else None
        except: return None
 
    def classify_event(self):
        """
        IMPROVED: Stricter confidence thresholds
        + Multi-frame consensus
        """
        now = time.time()
        if self.held_event != 'normal' and now < self.held_until:
            return self.held_event, self.held_conf, self.held_desc
        
        if len(self.y_smooth) < 8:  # ← Increased from 6 for more stability
            return 'normal', 0.0, 'Collecting data'
        
        ys = list(self.y_smooth)
        ws = list(self.w_buf)
        
        y_steps = [ys[i] - ys[i-1] for i in range(1, len(ys))]
        y_abs = [abs(s) for s in y_steps]
        w_steps = [ws[i] - ws[i-1] for i in range(1, len(ws))]
        
        max_step = max(y_abs) if y_abs else 0
        mean_step = sum(y_abs) / len(y_abs) if y_abs else 0
        mean_w_grow = sum(w_steps) / len(w_steps) if w_steps else 0
        
        # ── POTHOLE (Stricter: need 2 large steps) ──
        large_steps = sum(1 for s in y_abs if s > self.POTHOLE_STEP_PX * 0.5)
        if max_step > self.POTHOLE_STEP_PX and large_steps >= 2:
            conf = min(1.0, (max_step / 30.0) * (large_steps / 4.0))
            if conf > 0.6:  # ← Confidence filter
                self._hold('pothole', conf, f'Multi-impact {max_step:.0f}px')
                return self.held_event, self.held_conf, self.held_desc
        
        # ── SPEED HUMP (More frames required) ──
        if mean_step > self.HUMP_STEP_PX:
            sustained = sum(1 for s in y_abs if s > self.HUMP_STEP_PX * 0.6)
            if sustained >= self.HUMP_MIN_FRAMES + 2:  # ← +2 more frames
                conf = min(1.0, (sustained / 14.0) * (mean_step / 8.0))
                if conf > 0.55:  # ← Confidence filter
                    self._hold('speed_hump', conf, f'Sustained {mean_step:.1f}px/f')
                    return self.held_event, self.held_conf, self.held_desc
        
        # ── BRAKING (Higher threshold) ──
        if mean_w_grow > self.BRAKE_GROW_PX * 1.2 and mean_step < 8:
            conf = min(1.0, mean_w_grow / 10.0)  # Stricter
            if conf > 0.65:
                self._hold('braking', conf, f'Approaching +{mean_w_grow:.1f}px/f')
                return self.held_event, self.held_conf, self.held_desc
        
        self._hold('normal', 0.0, 'Road normal')
        return 'normal', 0.0, 'Road normal'
 
    def _hold(self, ev, conf, desc):
        if ev != 'normal':
            self.held_event = ev
            self.held_conf  = conf
            self.held_desc  = desc
            self.held_until = time.time() + self.HOLD_SEC
        elif time.time() >= self.held_until:
            self.held_event = 'normal'
            self.held_conf  = 0.0
            self.held_desc  = 'Road normal'
 
    def get_motion_score(self):
        ev,conf,_ = self.classify_event()
        return {
            'pothole':    min(5.0, 3.0+conf*2.0),
            'speed_hump': min(3.0, 1.0+conf*2.0),
            'braking':    min(2.5, 0.8+conf*1.5),
        }.get(ev, 0.0)
 
    def is_stale(self, t=1.2):
        return (time.time()-self.last_seen)>t
 
 
# ════════════════════════════════════════════════
class MotionDetectorYOLO:
 
    CLASS_NAMES = {2:'CAR',3:'MOTORCYCLE',5:'BUS',7:'TRUCK'}
    EV_COLORS   = {
        'normal':    (80,255,80),
        'pothole':   (40,40,240),
        'speed_hump':(0,165,255),
        'braking':   (0,210,255),
    }
    EV_LABELS = {
        'normal':    'NORMAL',
        'pothole':   'POTHOLE',
        'speed_hump':'SPEED HUMP',
        'braking':   'BRAKING',
    }
 
    def __init__(self):
        print("Loading YOLOv8 vehicle model...")
        self.model    = YOLO('yolov8n.pt')
        self.v_classes= [2,3,5,7]
        self.conf_thr = 0.35    # higher = fewer false detections
        self.min_area = 3500    # ignore tiny boxes
 
        self.vehicles = {}      # vid → TrackedVehicle
        self.next_id  = 0
        self.primary  = None
        # primary_mode controls how the "primary" vehicle is chosen
        # options: 'area' (largest bbox), 'distance' (closest by estimated distance),
        # 'center' (nearest to image center), 'confidence' (highest detection conf)
        self.primary_mode = 'area'
 
        print("Vehicle detector ready.")
 
    def _match(self, box):
        x1,y1,x2,y2=box
        cx,cy=(x1+x2)//2,(y1+y2)//2
        best_id,best_d=None,90
        for vid,tv in self.vehicles.items():
            tx1,ty1,tx2,ty2=tv.box
            tcx,tcy=(tx1+tx2)//2,(ty1+ty2)//2
            d=((cx-tcx)**2+(cy-tcy)**2)**0.5
            if d<best_d: best_d=d; best_id=vid
        return best_id
 
    def detect(self, frame):
        h,w = frame.shape[:2]
        annotated = frame.copy()
 
        # ── YOLO inference ──
        res = self.model(frame, verbose=False,
                         conf=self.conf_thr,
                         classes=self.v_classes)
 
        for r in res:
            for bd in r.boxes:
                x1,y1,x2,y2=map(int,bd.xyxy[0])
                conf=float(bd.conf[0])
                cls =int(bd.cls[0])
                if (x2-x1)*(y2-y1)<self.min_area: continue
                box=(x1,y1,x2,y2)
                vid=self._match(box)
                if vid is not None:
                    self.vehicles[vid].update(box,conf)
                    self.vehicles[vid].cls=cls
                else:
                    self.vehicles[self.next_id]=TrackedVehicle(
                        self.next_id,box,cls,conf)
                    self.next_id+=1
 
        # ── Remove stale vehicles (count resets dynamically) ──
        stale=[v for v,tv in self.vehicles.items() if tv.is_stale()]
        for v in stale: del self.vehicles[v]
 
        # ── Find primary according to `primary_mode` ──
        self.primary = None
        best_metric = -1e12
        img_cx = w / 2.0
        img_cy = h / 2.0
        for vid, tv in self.vehicles.items():
            # Exclude vehicles detected as oncoming from primary selection
            if getattr(tv, 'oncoming', False):
                continue
            x1, y1, x2, y2 = tv.box
            area = (x2 - x1) * (y2 - y1)

            if self.primary_mode == 'area':
                metric = float(area)
            elif self.primary_mode == 'distance':
                # Smaller distance = closer -> higher metric
                d = tv.get_distance_m()
                metric = -float(d) if d is not None else -1e6
            elif self.primary_mode == 'center':
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                dist_center = ((cx - img_cx) ** 2 + (cy - img_cy) ** 2) ** 0.5
                metric = -float(dist_center)
            elif self.primary_mode == 'confidence':
                metric = float(tv.conf)
            else:
                metric = float(area)

            if metric > best_metric:
                best_metric = metric
                self.primary = tv
 
        # ── Draw ALL vehicles ──
        for vid,tv in self.vehicles.items():
            x1,y1,x2,y2=tv.box
            is_p=(tv==self.primary)

            # If vehicle is oncoming, mark in red and reduce priority
            if getattr(tv, 'oncoming', False):
                col = (0,0,255)
                thk = 1
                ev = 'normal'
            else:
                if is_p:
                    ev,evc,evd = tv.classify_event()
                    col = self.EV_COLORS.get(ev,(80,255,80))
                    thk = 2
                else:
                    ev='normal'; col=(70,70,70); thk=1

            cv2.rectangle(annotated,(x1,y1),(x2,y2),col,thk)

            # ADAS corners on primary (only for non-oncoming primary)
            if is_p and not getattr(tv, 'oncoming', False):
                L=14
                for p1,p2 in [
                    ((x1,y1),(x1+L,y1)),((x1,y1),(x1,y1+L)),
                    ((x2,y1),(x2-L,y1)),((x2,y1),(x2,y1+L)),
                    ((x1,y2),(x1+L,y2)),((x1,y2),(x1,y2-L)),
                    ((x2,y2),(x2-L,y2)),((x2,y2),(x2,y2-L)),
                ]:
                    cv2.line(annotated,p1,p2,col,3)

            nm  =self.CLASS_NAMES.get(tv.cls,'VEH')
            lbl =f"{nm}#{vid} {tv.conf:.0%}"
            # If oncoming, prefix label
            if getattr(tv, 'oncoming', False):
                lbl = "ONC:" + lbl
            cv2.putText(annotated,lbl,(x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX,0.50,col,1,cv2.LINE_AA)

            if is_p and not getattr(tv, 'oncoming', False):
                dm=tv.get_distance_m()
                sp=tv.get_speed_kmh(dm)
                parts=[]
                if dm: parts.append(f"D:{dm}m")
                if sp: parts.append(f"S:{sp}km/h")
                if parts:
                    cv2.putText(annotated," ".join(parts),
                                (x1,y1-26),
                                cv2.FONT_HERSHEY_SIMPLEX,0.46,col,1,cv2.LINE_AA)
                if ev!='normal':
                    lbv=self.EV_LABELS.get(ev,'')
                    cv2.putText(annotated,f"{lbv} {evc*100:.0f}%",
                                (x1,y2+22),
                                cv2.FONT_HERSHEY_SIMPLEX,0.55,col,2,cv2.LINE_AA)
 
        # Vehicle count — bottom strip (exclude oncoming)
        count=sum(1 for tv in self.vehicles.values() if not getattr(tv, 'oncoming', False))
        cv2.rectangle(annotated,(0,h-22),(200,h),(0,0,0),-1)
        cv2.putText(annotated,f"VEHICLES TRACKED: {count}",
                    (6,h-7),cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,(0,229,255),1,cv2.LINE_AA)
 
        if self.primary:
            ms=self.primary.get_motion_score()
            vm=self.get_vertical_movement() if hasattr(
                self.primary,'y_smooth') else 0
            return ms,vm,annotated
        return 0.0,0.0,annotated
 
    def get_distance(self):
        return self.primary.get_distance_m() if self.primary else None
 
    def get_vehicle_speed(self):
        if not self.primary: return None
        d=self.primary.get_distance_m()
        return self.primary.get_speed_kmh(d)
 
    def get_vehicle_count(self):
        # Exclude oncoming vehicles from the reported count
        return sum(1 for tv in self.vehicles.values() if not getattr(tv, 'oncoming', False))   # live count — resets as vehicles leave
 
    def get_camera_event(self):
        if self.primary:
            return self.primary.classify_event()
        return 'normal',0.0,'No vehicle'
 
    def get_vertical_movement(self):
        if self.primary and len(self.primary.y_smooth)>=3:
            ys=list(self.primary.y_smooth)
            diffs=[abs(ys[i]-ys[i-1]) for i in range(1,len(ys))]
            return max(diffs) if diffs else 0.0
        return 0.0