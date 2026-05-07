import cv2
import numpy as np
import datetime
 
class Dashboard:
    """
    Clean, professional OpenCV dashboard panel.
    Crystal-clear layout. All info organized.
    Anti-aliased text. Color-coded sections.
    """
    W = 380    # panel width
 
    # Colors (BGR)
    BG     = (12, 18, 26)
    PANEL  = (18, 30, 44)
    BORDER = (30, 72, 102)
    CYAN   = (255, 210, 0)
    GREEN  = (60,  240, 60)
    ORANGE = (0,   155, 255)
    RED    = (30,  30,  230)
    WHITE  = (225, 242, 255)
    MUTED  = (80,  110, 130)
    YELLOW = (0,   200, 255)
    BLACK  = (0,   0,   0)
    DARK   = (8,   12,  18)
 
    SC = {'NORMAL':(60,240,60),'CAUTION':(0,155,255),'HAZARD':(30,30,230)}
    EC = {
        'NORMAL ROAD':(60,240,60),
        'POTHOLE'    :(30,30,230),
        'SPEED HUMP' :(0,155,255),
        'BRAKING'    :(0,200,255),
        'CRACK'      :(0,120,220),
    }
 
    def __init__(self):
        print("Dashboard ready.")
 
    # ── Primitives ──
    def _t(self, img, txt, x, y, col=None, s=0.42, th=1):
        cv2.putText(img,str(txt),(x,y),
                    cv2.FONT_HERSHEY_SIMPLEX,s,
                    col or self.MUTED,th,cv2.LINE_AA)
 
    def _bar(self, img, x, y, w, h, pct, col, bg=(20,38,54)):
        pct = min(max(float(pct),0.0),1.0)
        cv2.rectangle(img,(x,y),(x+w,y+h),bg,-1)
        fw=int(w*pct)
        if fw>0: cv2.rectangle(img,(x,y),(x+fw,y+h),col,-1)
        cv2.rectangle(img,(x,y),(x+w,y+h),self.BORDER,1)
 
    def _hdr(self, img, txt, y):
        """Section header with cyan accent line"""
        cv2.rectangle(img,(6,y-1),(self.W-6,y+13),(15,26,38),-1)
        self._t(img,txt,10,y+10,self.CYAN,0.33,1)
        cv2.line(img,(6,y+14),(self.W-6,y+14),self.BORDER,1)
        return y+20
 
    def _pill(self, img, x, y, w, h, col, txt, txt_col=None):
        """Rounded pill-shaped label"""
        overlay = img.copy()
        cv2.rectangle(overlay,(x,y),(x+w,y+h),col,-1)
        cv2.addWeighted(overlay,0.18,img,0.82,0,img)
        cv2.rectangle(img,(x,y),(x+w,y+h),col,1)
        self._t(img,txt,x+6,y+h-5,txt_col or col,0.38,1)
 
    def draw(self, frame, result,
             distance_m=None, vehicle_speed=None,
             vehicle_count=0,
             cam_event='NORMAL ROAD', cam_event_desc='',
             road_event='NORMAL ROAD', road_event_desc='',
             imu_event_conf=0):
 
        status  = str(result.get("decision",       "NORMAL"))
        motor   = int(result.get("motor_speed",    100))
        conf    = float(str(result.get("confidence",0)).replace('%',''))
        imu_z   = float(result.get("raw_imu",      1.0))
        motion  = float(result.get("raw_motion",   0.0))
        spike   = bool(result.get("imu_spike",     False))
        sev     = float(result.get("severity_score",0.0))
 
        sc  = self.SC.get(status, self.GREEN)
        h   = frame.shape[0]
        W   = self.W
 
        panel = np.full((h,W,3), self.BG, dtype=np.uint8)
 
        # ═══ TITLE ═══
        cv2.rectangle(panel,(0,0),(W,36),self.PANEL,-1)
        cv2.line(panel,(0,36),(W,36),sc,2)
        self._t(panel,"ADAS ROAD HAZARD SYSTEM",8,24,self.CYAN,0.48,1)
        ts=datetime.datetime.now().strftime("%H:%M:%S")
        self._t(panel,ts,W-62,24,self.MUTED,0.36,1)
 
        y=44
 
        # ═══ SYSTEM STATUS ═══
        y=self._hdr(panel,"SYSTEM STATUS",y)
        # Large status pill
        cv2.rectangle(panel,(8,y),(W-8,y+32),sc,1)
        ov=panel.copy()
        cv2.rectangle(ov,(9,y+1),(W-9,y+31),sc,-1)
        cv2.addWeighted(ov,0.12,panel,0.88,0,panel)
        self._t(panel,status,14,y+23,sc,0.80,2)
 
        # Event type pills (camera + road side by side)
        cam_c  = self.EC.get(cam_event,  self.GREEN)
        road_c = self.EC.get(road_event, self.GREEN)
        self._pill(panel,14,y+36,W//2-20,16,cam_c,
                   f"CAM:{cam_event[:10]}")
        self._pill(panel,W//2+4,y+36,W//2-18,16,road_c,
                   f"RD:{road_event[:10]}")
        y+=58
 
        # Descriptions
        if cam_event_desc and 'normal' not in cam_event.lower():
            self._t(panel,f"  {cam_event_desc[:38]}",8,y,cam_c,0.34)
            y+=13
        if road_event_desc and 'normal' not in road_event.lower():
            self._t(panel,f"  {road_event_desc[:38]}",8,y,road_c,0.34)
            y+=13
        y+=4
 
        # ═══ MOTOR SPEED ═══
        y=self._hdr(panel,"RECOMMENDED MOTOR SPEED",y)
        mc=(self.RED if motor<40 else self.ORANGE if motor<70 else self.GREEN)
        self._bar(panel,8,y,W-16,16,motor/100,mc)
        self._t(panel,f"{motor}%",W-52,y+13,mc,0.52,1)
        y+=22
        rec=("Full speed — road clear"   if motor==100 else
             "Slow down — caution ahead" if motor>=70  else
             "Reduce speed — hazard"     if motor>=40  else
             "BRAKE — severe hazard")
        self._t(panel,rec,10,y,mc,0.36)
        y+=16
 
        # ═══ VEHICLE INFO ═══
        y=self._hdr(panel,"FRONT VEHICLE",y)
 
        # Distance
        if distance_m is not None:
            dc=(self.RED if distance_m<3 else
                self.ORANGE if distance_m<8 else self.GREEN)
            wn=("TOO CLOSE!" if distance_m<3 else
                "MAINTAIN"   if distance_m<8 else "SAFE")
            self._t(panel,f"Distance : {distance_m}m  [{wn}]",10,y,dc,0.44,1)
            self._bar(panel,8,y+4,W-16,5,max(0,1-distance_m/20),dc)
            y+=18
        else:
            self._t(panel,"Distance : No vehicle",10,y,self.MUTED,0.42)
            y+=16
 
        # Speed
        if vehicle_speed is not None:
            vc=(self.RED if vehicle_speed>60 else
                self.ORANGE if vehicle_speed>30 else self.GREEN)
            self._t(panel,f"Speed    : {vehicle_speed} km/h",10,y,vc,0.44,1)
            self._bar(panel,8,y+4,W-16,5,min(vehicle_speed/80,1),vc)
            y+=18
        else:
            self._t(panel,"Speed    : Not tracked",10,y,self.MUTED,0.42)
            y+=16
 
        # Vehicle count (dynamic — resets as vehicles leave frame)
        vc=int(vehicle_count)
        vcc=self.GREEN if vc>0 else self.MUTED
        self._t(panel,f"Vehicles : {vc} in frame",10,y,vcc,0.42)
        # Small vehicle count dots
        for i in range(min(vc,6)):
            cv2.circle(panel,(W-20-i*14,y-4),5,self.GREEN,-1)
        y+=16
 
        # ═══ IMU ═══
        y=self._hdr(panel,"IMU SENSOR (Secondary)",y)
        ic=(self.RED if imu_z>2.3 else
            self.ORANGE if imu_z>1.8 else self.GREEN)
        self._bar(panel,8,y,W-16,12,min(imu_z/3.5,1),ic)
        itag="SPIKE" if imu_z>2.3 else "HIGH" if imu_z>1.8 else "NORMAL"
        self._t(panel,f"{imu_z:.3f}g  [{itag}]",10,y+24,ic,0.44)
        y+=34
 
        # ═══ CAMERA MOTION ═══
        y=self._hdr(panel,"CAMERA MOTION",y)
        cc=(self.RED if motion>2 else self.ORANGE if motion>0.8 else self.GREEN)
        self._bar(panel,8,y,W-16,12,min(motion/5,1),cc)
        ctag="HIGH" if motion>0.8 else "LOW"
        self._t(panel,f"{motion:.2f}  [{ctag}]",10,y+24,cc,0.44)
        y+=34
 
        # ═══ CONFIDENCE / SEVERITY (side by side) ═══
        y=self._hdr(panel,"ML CONFIDENCE  |  SEVERITY",y)
        hw=(W-20)//2
        self._bar(panel,8,y,hw,10,min(conf/100,1),self.CYAN)
        self._t(panel,f"Conf:{conf:.0f}%",10,y+22,self.CYAN,0.40)
        sc2=(self.RED if sev>0.6 else self.ORANGE if sev>0.3 else self.GREEN)
        self._bar(panel,hw+12,y,hw,10,sev,sc2)
        sv=("HIGH" if sev>0.6 else "MED" if sev>0.3 else "LOW")
        self._t(panel,f"Sev:{sev:.2f}[{sv}]",hw+14,y+22,sc2,0.40)
        y+=34
 
        # ═══ SENSOR STATUS ═══
        y=self._hdr(panel,"SENSOR STATUS",y)
        items=[
            (self.RED if spike else self.GREEN, "IMU Sensor"),
            (self.GREEN if motion>0 else self.ORANGE, "Camera"),
            (self.CYAN,  "ML Model"),
            (self.YELLOW,"YOLO v8"),
        ]
        for i,(col,lbl) in enumerate(items):
            col2,col3 = i//2, i%2
            xo = col3*(W//2)
            yo = y + col2*16
            cv2.circle(panel,(xo+14,yo+4),5,col,-1)
            self._t(panel,lbl,xo+24,yo+8,self.WHITE,0.37)
        y+=34
 
        # ═══ ALERT BANNER ═══
        if status!='NORMAL':
            bh=34; by=h-bh
            sc3=self.SC.get(status,self.GREEN)
            cv2.rectangle(panel,(0,by),(W,h),sc3,-1)
            msg=("!! HAZARD — REDUCING SPEED NOW !!"
                 if status=='HAZARD' else
                 "  CAUTION — MONITORING ROAD AHEAD")
            cv2.putText(panel,msg,(6,by+22),
                        cv2.FONT_HERSHEY_SIMPLEX,0.44,
                        self.BLACK,1,cv2.LINE_AA)
 
        return np.hstack([frame, panel])