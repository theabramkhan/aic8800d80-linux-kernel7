#!/usr/bin/env python3
# Patch AIC aic8800 v1.0.9 (BrosTrend) driver source to build and bind on Linux 7.1+
# for AIC8800D80/D81 USB WiFi6 dongles that use vendor ID 0x368B (e.g. 368b:8d81).
# WiFi only (Bluetooth is not supported by this driver). Idempotent & self-checking.
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
FDRV = os.path.join(ROOT, "aic8800_fdrv")
G, NL = "#if (LINUX_VERSION_CODE >= KERNEL_VERSION(7, 1, 0))", "\n"
def rl(p):
    with open(p,"r",encoding="utf-8",newline="") as f: return f.readlines()
def rt(p):
    with open(p,"r",encoding="utf-8",newline="") as f: return f.read()
def wr(p,d):
    with open(p,"w",encoding="utf-8",newline="") as f: f.write(d)
done=[]

# 0) Makefile: Fedora builds modules with -Werror; our warnings must not be fatal
mk=os.path.join(FDRV,"Makefile"); t=rt(mk)
if "-Wno-error" not in t:
    t=(t if t.endswith("\n") else t+"\n")+"ccflags-y += -Wno-error -Wno-restrict -Wno-missing-prototypes\n"
    wr(mk,t); done.append("Makefile (-Wno-error)")

# 1) rwnx_main.c: cfg80211 ops changed 2nd arg net_device -> wireless_dev in 7.1
main=os.path.join(FDRV,"rwnx_main.c"); L=rl(main)
if "KERNEL_VERSION(7, 1, 0)" not in "".join(L):
    funcs=[(2791,"netdev"),(2887,"netdev"),(2906,"netdev"),(2961,"netdev"),
           (3278,"dev"),(3429,"dev"),(3720,"dev"),(5684,"dev"),(5726,"dev")]
    for start,name in sorted(funcs,reverse=True):
        s=start-1
        brace=next((i for i in range(s,min(s+200,len(L))) if L[i].strip()=="{"),None)
        pat="struct net_device *%s,"%name
        param=next((i for i in range(s,brace+1) if pat in L[i]),None)
        if brace is None or param is None: sys.exit("rwnx_main.c: anchors moved (source version mismatch)")
        L[brace+1:brace+1]=[G+NL,"\tstruct net_device *%s = wdev->netdev;"%name+NL,"#endif"+NL]
        L[param]=L[param].replace(pat,NL+G+NL+"\tstruct wireless_dev *wdev,"+NL+"#else"+NL+"\t"+pat+NL+"#endif",1)
    txt="".join(L)
    def gc(txt,anchor,new,expect):
        c=0;i=0;lines=txt.split("\n");out=[]
        for ln in lines:
            p=ln.find(anchor);cm=ln.find("//")
            if p!=-1 and not(cm!=-1 and cm<p):
                out+=[G,new,"#else",ln,"#endif"];c+=1
            else: out.append(ln)
        if c!=expect: sys.exit("rwnx_main.c: call-site '%s' x%d (expected %d)"%(anchor,c,expect))
        return "\n".join(out)
    txt=gc(txt,"cfg80211_new_sta(rwnx_vif->ndev, sta->mac_addr, &sinfo, GFP_KERNEL);",
           "                        cfg80211_new_sta(&rwnx_vif->wdev, sta->mac_addr, &sinfo, GFP_KERNEL);",1)
    txt=gc(txt,"cfg80211_del_sta(rwnx_vif->ndev, cur->mac_addr, GFP_KERNEL);",
           "                        cfg80211_del_sta(&rwnx_vif->wdev, cur->mac_addr, GFP_KERNEL);",1)
    txt=gc(txt,"rwnx_cfg80211_add_key(wiphy, dev,",
           "        rwnx_cfg80211_add_key(wiphy, dev->ieee80211_ptr,",1)
    txt=gc(txt,"rwnx_cfg80211_del_station_compat(wiphy, dev, NULL);",
           "        rwnx_cfg80211_del_station_compat(wiphy, dev->ieee80211_ptr, NULL);",1)
    wr(main,txt); done.append("rwnx_main.c (cfg80211 wireless_dev ops)")

# 2) rwnx_tdls.c: ieee80211_mgmt action union restructured in 7.1 -> compile out TDLS discover
tp=os.path.join(FDRV,"rwnx_tdls.c"); L=rl(tp)
if "KERNEL_VERSION(7, 1, 0)" not in "".join(L):
    ci=next((i for i,l in enumerate(L) if "case WLAN_PUB_ACTION_TDLS_DISCOVER_RES:" in l),None)
    bi=next((i for i in range(ci,ci+25) if L[i].strip()=="break;"),None) if ci is not None else None
    if ci is None or bi is None: sys.exit("rwnx_tdls.c: anchors moved")
    L.insert(bi+1,"#endif\n"); L.insert(ci,"#if (LINUX_VERSION_CODE < KERNEL_VERSION(7, 1, 0))\n")
    wr(tp,"".join(L)); done.append("rwnx_tdls.c (TDLS action union)")

# 3) rwnx_events.h: dead tracepoint union field -> valid .category (all kernels)
ep=os.path.join(FDRV,"rwnx_events.h"); t=rt(ep)
old="mgmt->u.action.u.wme_action.action_code"
if old in t:
    wr(ep,t.replace(old,"mgmt->u.action.category")); done.append("rwnx_events.h (tracepoint field)")

# 4) aicwf_usb.c: add USB id for vendor 0x368B + product 0x8d81 (368b:8d81)
up=os.path.join(FDRV,"aicwf_usb.c"); L=rl(up)
if not any("USB_VENDOR_ID_AIC_V2, USB_PRODUCT_ID_AIC8800D81," in l for l in L):
    anc="{USB_DEVICE_AND_INTERFACE_INFO(USB_VENDOR_ID_AIC, USB_PRODUCT_ID_AIC8800D81, 0xff, 0xff, 0xff)}"
    idx=next((i for i,l in enumerate(L) if anc in l),None)
    if idx is None: sys.exit("aicwf_usb.c: id_table anchor moved")
    L.insert(idx+1,"    {USB_DEVICE_AND_INTERFACE_INFO(USB_VENDOR_ID_AIC_V2, USB_PRODUCT_ID_AIC8800D81, 0xff, 0xff, 0xff)},\r\n")
    wr(up,"".join(L)); done.append("aicwf_usb.c (368b:8d81 device id)")

if done: print("Applied:\n  - "+"\n  - ".join(done))
else: print("Already patched (no changes needed).")
