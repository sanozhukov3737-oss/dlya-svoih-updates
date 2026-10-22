package ru.dlyasvoih.app.ui.screens

import android.content.Context
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.view.InputDevice
import android.view.MotionEvent
import android.webkit.WebView
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.test.core.app.ApplicationProvider
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class PmnVisualCheckTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var viewer: WebView
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()

    private fun evaluate(script: String): String {
        val answer = AtomicReference<String>()
        val latch = CountDownLatch(1)
        instrumentation.runOnMainSync {
            viewer.evaluateJavascript(script) { answer.set(it); latch.countDown() }
        }
        check(latch.await(8, TimeUnit.SECONDS)) { "WebView JavaScript timed out" }
        return answer.get()
    }

    private fun shell(command: String): ByteArray = ParcelFileDescriptor.AutoCloseInputStream(
        instrumentation.uiAutomation.executeShellCommand(command)).use { it.readBytes() }

    private fun frame(name: String) {
        val latch = CountDownLatch(1)
        instrumentation.runOnMainSync {
            viewer.postVisualStateCallback(SystemClock.uptimeMillis(), object : WebView.VisualStateCallback() {
                override fun onComplete(requestId: Long) { latch.countDown() }
            })
        }
        assertTrue("No composited WebView frame", latch.await(12, TimeUnit.SECONDS))
        Thread.sleep(500)
        shell("screencap -p /data/local/tmp/pmn-visual-proof/$name.png")
    }

    private fun snapshot(): JSONObject = JSONObject(evaluate("""
        (() => {
          const c=document.querySelector('canvas'),ctx=c.getContext('2d');
          const p=ctx.getImageData(0,0,c.width,c.height).data;
          let hash=2166136261,model=0,brown=0,olive=0,yellow=0;
          let minX=c.width,minY=c.height,maxX=-1,maxY=-1,changed=0;
          for(let i=0;i<p.length;i+=4){
            const r=p[i],g=p[i+1],b=p[i+2];
            hash=Math.imul(hash^r,16777619);hash=Math.imul(hash^g,16777619);hash=Math.imul(hash^b,16777619);
            if(Math.abs(r-231)+Math.abs(g-233)+Math.abs(b-228)>25){
              model++;const x=(i/4)%c.width,y=Math.floor(i/4/c.width);
              minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
              if(r>g*1.15&&g>b*1.10&&r>55)brown++;
              if(g>=r*.92&&g>b*1.05&&g<210)olive++;
              if(r>100&&g>90&&r/g>.95&&r/g<1.4&&b/g<.85&&r-b>28)yellow++;
            }
            if(window.__pmnBefore&&Math.abs(r-window.__pmnBefore[i])+Math.abs(g-window.__pmnBefore[i+1])+Math.abs(b-window.__pmnBefore[i+2])>30)changed++;
          }
          const draws=window.__pmnDraws||[];let maxGap=0;
          for(let i=1;i<draws.length;i++)maxGap=Math.max(maxGap,draws[i]-draws[i-1]);
          return {state:document.body.dataset.state,id:document.body.dataset.model,hash:String(hash>>>0),
            triangles:Number(c.dataset.triangles),colors:Number(c.dataset.colors),homeExtent:Number(c.dataset.homeExtent),
            canvas:[c.width,c.height],modelPixels:model,brownPixels:brown,olivePixels:olive,markingPixels:yellow,
            bounds:[minX,minY,maxX,maxY],changedFraction:changed/(c.width*c.height),drawFrames:draws.length,maxDrawGapMs:maxGap};
        })()
    """))

    private fun pinchOut() {
        val size = AtomicReference<Pair<Int, Int>>()
        instrumentation.runOnMainSync { size.set(viewer.width to viewer.height) }
        val (w, h) = size.get(); val down = SystemClock.uptimeMillis()
        fun send(action: Int, count: Int, spread: Float) {
            val properties = Array(count) { i -> MotionEvent.PointerProperties().apply {
                id=i; toolType=MotionEvent.TOOL_TYPE_FINGER
            } }
            val coords = Array(count) { i -> MotionEvent.PointerCoords().apply {
                x=w*.5f+(if(i==0)-spread else spread);y=h*.56f;pressure=1f;size=1f
            } }
            val event = MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,count,
                properties,coords,0,0,1f,1f,0,0,InputDevice.SOURCE_TOUCHSCREEN,0)
            instrumentation.runOnMainSync { viewer.dispatchTouchEvent(event) }
            event.recycle()
        }
        send(MotionEvent.ACTION_DOWN,1,40f)
        send(MotionEvent.ACTION_POINTER_DOWN or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,40f)
        for(i in 1..16){send(MotionEvent.ACTION_MOVE,2,40f+i*3f);Thread.sleep(25)}
        send(MotionEvent.ACTION_POINTER_UP or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,88f)
        send(MotionEvent.ACTION_UP,1,88f)
    }

    @Test fun approvedPmnRendersRotatesZoomsAndResetsOffline() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val result = JSONObject().put("api",Build.VERSION.SDK_INT).put("modelId","pmn-visual-prototype")
        shell("mkdir -p /data/local/tmp/pmn-visual-proof")
        compose.setContent { MaterialTheme {
            OfflineModelDialog(modelId="pmn-visual-prototype",onViewerCreated={viewer=it},onDismiss={})
        } }
        compose.waitForIdle()
        compose.onNodeWithTag("offline_3d_webview").assertIsDisplayed()
        try {
            val deadline = SystemClock.uptimeMillis()+45_000
            var state = ""
            while(SystemClock.uptimeMillis()<deadline){
                state=evaluate("document.body&&document.body.dataset.state")
                if(state=="\"ready\""||state=="\"error\"")break
                Thread.sleep(100)
            }
            assertEquals(evaluate("document.body.innerText"),"\"ready\"",state)
            instrumentation.runOnMainSync {
                assertTrue(viewer.settings.blockNetworkLoads)
                assertFalse(viewer.settings.allowFileAccess)
                assertFalse(viewer.settings.allowContentAccess)
                result.put("networkLoadsBlocked",viewer.settings.blockNetworkLoads)
                result.put("webView",WebView.getCurrentWebViewPackage()?.let { it.packageName+" "+it.versionName })
            }
            frame("initial")
            val initial=snapshot();result.put("initial",initial)
            assertEquals("pmn-visual-prototype",initial.getString("id"))
            assertEquals(10_700,initial.getInt("triangles"))
            assertTrue("Model is clipped at home",initial.getDouble("homeExtent")<=.85)
            assertTrue("Brown body is not visible",initial.getInt("brownPixels")>500)
            assertTrue("Dark cover is not visible",initial.getInt("olivePixels")>1000)
            assertTrue("Marking contrast is missing",initial.getInt("markingPixels")>25)
            evaluate("""(() => {
                const ctx=document.querySelector('canvas').getContext('2d');
                const c=ctx.canvas;window.__pmnBefore=ctx.getImageData(0,0,c.width,c.height).data;
                window.__pmnDraws=[];const original=ctx.drawImage.bind(ctx);
                ctx.drawImage=function(...args){original(...args);window.__pmnDraws.push(performance.now())};
                return true;
            })()""")
            val location = IntArray(2)
            val size = AtomicReference<Pair<Int,Int>>()
            instrumentation.runOnMainSync { viewer.getLocationOnScreen(location);size.set(viewer.width to viewer.height) }
            val (w,h)=size.get()
            val x1=location[0]+(w*.30).toInt();val x2=location[0]+(w*.68).toInt()
            val y=location[1]+(h*.58).toInt()
            shell("input swipe $x1 $y $x2 $y 700")
            frame("rotated")
            val rotated=snapshot();result.put("rotated",rotated)
            assertTrue("Swipe did not change the actual model image",rotated.getDouble("changedFraction")>.02)
            assertTrue("Swipe did not produce multiple rendered frames",rotated.getInt("drawFrames")>=2)
            evaluate("document.getElementById('reset').click()")
            frame("reset")
            val reset=snapshot();result.put("reset",reset)
            assertTrue("Reset did not restore the home view",reset.getDouble("changedFraction")<.005)
            pinchOut();frame("zoomed")
            val zoomed=snapshot();result.put("zoomed",zoomed)
            assertTrue("Two-finger pinch did not enlarge the model",zoomed.getInt("modelPixels")>initial.getInt("modelPixels")*1.08)
            result.put("passed",true).put("performanceScope","Software GPU Android emulator; not a phone FPS benchmark")
            File(context.filesDir,"pmn-visual-result.json").writeText(result.toString(2))
        } catch(error:Throwable){
            result.put("passed",false).put("error",error.toString())
            File(context.filesDir,"pmn-visual-result.json").writeText(result.toString(2))
            shell("screencap -p /data/local/tmp/pmn-visual-proof/failure.png")
            throw error
        }
    }
}
