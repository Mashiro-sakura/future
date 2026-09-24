<script>
export default {
  onLaunch() {
    console.log('Future analysis miniapp launched')
  }
}
</script>

<style>
page {
  min-height: 100%;
  background: #0b0e17;
  color: #e6eaf2;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

view,
text {
  box-sizing: border-box;
}

.page {
  min-height: 100vh;
  padding: 24rpx;
}

.panel {
  border: 1rpx solid #1f2637;
  border-radius: 8rpx;
  background: #131826;
}

.muted {
  color: #7d879c;
}

.positive {
  color: #f0455c;
}

.negative {
  color: #0dbf7e;
}
</style>

